#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""validate_labels.py -- structural checker for tools/agx-isa/validation.json (DOC-02).

Verifies that the per-field evidence sidecar is complete and self-consistent against
tools/agx-isa/db.json, per docs/evidence-classification.md.

Hard checks (any failure -> exit 1):
  1. every db.json mnemonic is present in validation.json, and every field of every
     db.json descriptor has an entry (plus a `_instruction` entry per mnemonic);
  2. every `label` is exactly one of the eight labels in the spec's section 2;
  3. every non-`untested` label carries a non-empty `evidence` list;
  4. every `hardware-run` entry carries a `range` that is not the placeholder "tested";
  5. `untested` entries carry `evidence: []` (the spec's default rule);
  6. every entry has a non-empty `range` and a `target` in {M4, A18, M4+A18};
  7. no validation.json entry names a mnemonic/field that db.json does not have;
  8. the `coverage` block's counts agree with the entries actually present;
  9. `emitter_role: "data-word"` in db.json agrees exactly with the descriptor's own
     committed semantics phrase "NOT A STANDALONE HARDWARE OPCODE" (neither may drift).

EMITTABILITY DENOMINATOR (corrected, 2026-08-29).  The headline used to read
"N of <every descriptor in db.json>".  That mixes two populations:

  * INSTRUCTIONS an emitter must be able to produce, with operands to choose; and
  * DECODE SCAFFOLDING -- descriptors that exist only so the tokenizer can account for
    DATA bytes sitting between instructions.  Nobody emits a pad word; an emitter emits
    an instruction whose encoding happens to include those bytes.

"Emittable" is not defined for the second population, so counting it in the denominator
is a metric defect, not an ISA gap (EXP-0148, analysis/scaffolding_classification.md
section 3, c1-c2).  The scaffolding set is DERIVED from each descriptor's own committed
semantics -- the six that already say "NOT A STANDALONE HARDWARE OPCODE" -- and carried
in db.json as `emitter_role: "data-word"`, so the exclusion is auditable per descriptor
rather than a hand-maintained list here.  Both numbers are always printed.

Deliberately NOT excluded, because the committed evidence does not settle them:
  * the 3 continuation-word CANDIDATES (frame_marker_compact, n2_compact2,
    b_alu14_prep2) -- EXP-0148 records all three as unresolved, and its own 12-byte
    simd_shuffle variant REGRESSED when measured;
  * cubearray_coord_const -- 0 corpus firings, but EXP-0148 refuses to delete it without
    a texture-stage splice;
  * the 13 genuine-but-under-characterized instructions -- those are real ISA gaps.
They are reported as an informational lower bound only.

Soft check (warning only, exit code unaffected): db_sha256 vs the current db.json.

Usage:  python3 tools/agx-isa/validate_labels.py [--db PATH] [--labels PATH] [-q]
"""
import argparse
import hashlib
import json
import os
import sys

LABELS = (
    "hardware-run",
    "isolated-byte-diff",
    "corpus-correlation",
    "tokenization-only",
    "single-template-inference",
    "api-accept-reject",
    "host-private",
    "untested",
)
EMIT_OK = ("hardware-run", "isolated-byte-diff")
TARGETS = ("M4", "A18", "M4+A18")
HERE = os.path.dirname(os.path.abspath(__file__))

# A descriptor is DECODE SCAFFOLDING (excluded from the emittability denominator)
# iff db.json marks it `emitter_role: "data-word"`.  That mark must agree with the
# descriptor's own committed semantics phrase, which is what actually establishes it.
DATA_WORD_ROLE = "data-word"
DATA_WORD_PHRASE = "NOT A STANDALONE HARDWARE OPCODE"

# EXP-0148 scaffolding classification, reported as an informational lower bound.
# NOT excluded from the denominator -- every one of these is recorded UNRESOLVED there.
UNRESOLVED_SCAFFOLDING = (
    "frame_marker_compact",   # (a)-probable continuation of tg_atomic_prep; residual UNKNOWN
    "n2_compact2",            # (a)-probable continuation of simd_shuffle; 12-byte variant REGRESSED
    "b_alu14_prep2",          # (a) vs (b) undecided; needs one splice
    "cubearray_coord_const",  # 0 corpus firings, over-fitted match; do not delete without a splice
)


def check_entry(where, e, errors):
    if not isinstance(e, dict):
        errors.append("%s: entry is not an object" % where)
        return
    label = e.get("label")
    if label not in LABELS:
        errors.append("%s: label %r is not one of the eight spec labels" % (where, label))
        return
    ev = e.get("evidence")
    if not isinstance(ev, list):
        errors.append("%s: evidence must be a list" % where)
        ev = []
    if label != "untested" and not ev:
        errors.append("%s: label %r has an empty evidence list "
                      "(a label with no experiment pointer must be `untested`)" % (where, label))
    if label == "untested" and ev:
        # `untested` WITH evidence is legitimate and is the stronger of the two:
        # it means "an experiment swept this field and could not establish a model"
        # (EXP-0139's tested-but-unexplained convention), as opposed to "nobody has
        # looked". The distinction matters to whoever picks the field up next, so it
        # is preserved rather than flattened -- but it must say so, in `note`, or the
        # reader cannot tell which kind of `untested` they are holding.
        if not (e.get("note") or "").strip():
            errors.append("%s: label `untested` carries evidence %r but no `note`. "
                          "A swept-but-unexplained field must record what was tried and "
                          "what was seen; a genuinely unexamined field must have "
                          "evidence []." % (where, ev))
    rng = e.get("range")
    if not isinstance(rng, str) or not rng.strip():
        errors.append("%s: missing or empty `range`" % where)
    elif label == "hardware-run" and rng.strip().lower() == "tested":
        errors.append("%s: `hardware-run` range is the placeholder \"tested\" -- state the "
                      "parameter interval actually exercised, in the field's own units" % where)
    tgt = e.get("target")
    if tgt not in TARGETS:
        errors.append("%s: target %r is not one of %s" % (where, tgt, ", ".join(TARGETS)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "db.json"))
    ap.add_argument("--labels", default=os.path.join(HERE, "validation.json"))
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    db_raw = open(args.db, "rb").read()
    db = json.loads(db_raw.decode("utf-8"))
    val = json.load(open(args.labels))

    errors = []
    warnings = []

    sha = hashlib.sha256(db_raw).hexdigest()
    if val.get("db_sha256") != sha:
        warnings.append("db_sha256 in validation.json (%s) does not match the current db.json "
                        "(%s) -- labels may be stale" % (val.get("db_sha256"), sha))

    instrs = val.get("instructions")
    if not isinstance(instrs, dict):
        print("FAIL: validation.json has no `instructions` object", file=sys.stderr)
        return 1

    counts = {k: 0 for k in LABELS}
    n_fields = 0
    emittable = []
    db_names = set()
    data_words = []
    zero_field = []

    for ins in db["instructions"]:
        m = ins["mnemonic"]
        db_names.add(m)
        # check 9: the machine-readable role and the committed prose must agree.
        role = ins.get("emitter_role")
        says = DATA_WORD_PHRASE in ins.get("semantics", "")
        if role == DATA_WORD_ROLE:
            data_words.append(m)
            if not says:
                errors.append("instructions[%s]: emitter_role=%r but the semantics do not say "
                              "%r -- the exclusion must rest on the descriptor's own committed "
                              "evidence" % (m, role, DATA_WORD_PHRASE))
        elif says:
            errors.append("instructions[%s]: semantics say %r but emitter_role is %r -- mark it "
                          "%r or the emittability denominator silently counts a data word as an "
                          "un-emittable instruction"
                          % (m, DATA_WORD_PHRASE, role, DATA_WORD_ROLE))
        elif role is not None:
            errors.append("instructions[%s]: unknown emitter_role %r" % (m, role))
        if not ins.get("fields"):
            zero_field.append(m)
        entry = instrs.get(m)
        if entry is None:
            errors.append("instructions[%s]: MISSING from validation.json" % m)
            continue
        if "_instruction" not in entry:
            errors.append("instructions[%s]: missing `_instruction` entry" % m)
        else:
            check_entry("instructions[%s]._instruction" % m, entry["_instruction"], errors)
        fields = ins.get("fields", [])
        all_emit = True
        for f in fields:
            n = f["name"]
            if n not in entry:
                errors.append("instructions[%s].%s: MISSING label for a db.json field" % (m, n))
                all_emit = False
                continue
            where = "instructions[%s].%s" % (m, n)
            check_entry(where, entry[n], errors)
            lab = entry[n].get("label")
            if lab in counts:
                counts[lab] += 1
            n_fields += 1
            if lab not in EMIT_OK:
                all_emit = False
        if not fields:
            all_emit = entry.get("_instruction", {}).get("label") in EMIT_OK
        note = (entry.get("_instruction") or {}).get("note", "")
        if "EMITTABLE VETO" in note:
            all_emit = False
        if all_emit:
            emittable.append(m)
        extra = set(entry) - {"_instruction"} - {f["name"] for f in fields}
        for x in sorted(extra):
            errors.append("instructions[%s].%s: not a field of this db.json descriptor" % (m, x))

    for m in sorted(set(instrs) - db_names):
        errors.append("instructions[%s]: mnemonic is not in db.json" % m)

    cov = val.get("coverage") or {}
    if cov.get("total_instructions") != len(db["instructions"]):
        errors.append("coverage.total_instructions=%r but db.json has %d instructions"
                      % (cov.get("total_instructions"), len(db["instructions"])))
    if cov.get("total_fields") != n_fields:
        errors.append("coverage.total_fields=%r but %d field entries were checked"
                      % (cov.get("total_fields"), n_fields))
    by = cov.get("by_label") or {}
    for k in LABELS:
        if by.get(k, 0) != counts[k]:
            errors.append("coverage.by_label[%s]=%r but %d entries carry that label"
                          % (k, by.get(k), counts[k]))
    if sorted(cov.get("emittable_mnemonics") or []) != sorted(emittable):
        errors.append("coverage.emittable_mnemonics=%r but the emittable rule yields %r"
                      % (cov.get("emittable_mnemonics"), sorted(emittable)))
    if cov.get("emittable_instructions") != len(emittable):
        errors.append("coverage.emittable_instructions=%r but %d instructions qualify"
                      % (cov.get("emittable_instructions"), len(emittable)))

    # --- corrected emittability metric -------------------------------------
    dw = sorted(data_words)
    emitter_relevant = [i["mnemonic"] for i in db["instructions"]
                        if i.get("emitter_role") != DATA_WORD_ROLE]
    emit_rel = [m for m in emittable if m not in set(dw)]
    # Cross-check only the keys validation.json actually carries, so a validation.json
    # written before this metric existed still validates instead of hard-failing.
    for key, want in (("data_word_descriptors", len(dw)),
                      ("data_word_mnemonics", dw),
                      ("emitter_relevant_instructions", len(emitter_relevant)),
                      ("emittable_of_emitter_relevant", len(emit_rel))):
        if key in cov and cov[key] != want:
            errors.append("coverage.%s=%r but the corrected metric yields %r"
                          % (key, cov[key], want))

    for w in warnings:
        print("WARN: %s" % w, file=sys.stderr)
    if errors:
        for e in errors:
            print("FAIL: %s" % e, file=sys.stderr)
        print("\n%d violation(s)." % len(errors), file=sys.stderr)
        return 1
    if not args.quiet:
        print("OK: %d instructions, %d fields, all labels valid." %
              (len(db["instructions"]), n_fields))
        for k in LABELS:
            print("  %-26s %4d  (%4.1f%%)" % (k, counts[k], 100.0 * counts[k] / n_fields))
        n_all = len(db["instructions"])
        n_rel = len(emitter_relevant)
        print()
        print("  EMITTABILITY")
        print("    old headline (every db.json descriptor):      %3d / %3d  (%4.1f%%)"
              % (len(emittable), n_all, 100.0 * len(emittable) / n_all))
        print("    corrected (emitter-relevant instructions):    %3d / %3d  (%4.1f%%)"
              % (len(emit_rel), n_rel, 100.0 * len(emit_rel) / n_rel))
        print("      denominator = %d descriptors - %d data words" % (n_all, len(dw)))
        print("      data words excluded (own committed semantics say they are not")
        print("      standalone hardware opcodes -- an emitter never emits one):")
        for m in dw:
            print("        - %s" % m)
        unres = [m for m in UNRESOLVED_SCAFFOLDING if m in db_names]
        if unres:
            n_lb = n_rel - len(unres)
            print("    informational lower bound, NOT the headline:  %3d / %3d  (%4.1f%%)"
                  % (len([m for m in emit_rel if m not in set(unres)]), n_lb,
                     100.0 * len([m for m in emit_rel if m not in set(unres)]) / n_lb))
            print("      also setting aside %d scaffolding descriptors EXP-0148 leaves"
                  % len(unres))
            print("      UNRESOLVED (3 continuation-word candidates + 1 unreachable):")
            for m in unres:
                print("        - %s" % m)
        if zero_field:
            print("    zero-field descriptors (fully match-pinned, nothing to synthesize):")
            for m in sorted(zero_field):
                lab = (instrs[m].get("_instruction") or {}).get("label")
                print("        - %-22s %s%s" % (m, lab,
                      "  [byte-invariance REFUTED by EXP-0146]" if m == "sfu_marker" else ""))
            print("      These are IN the denominator: `emittable` is decided by their")
            print("      `_instruction` label, which is a validation.json decision, not a")
            print("      db.json one. Reported so the label owner can rule on them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
