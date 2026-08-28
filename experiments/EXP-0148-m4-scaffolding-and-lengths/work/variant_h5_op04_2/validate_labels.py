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
  8. the `coverage` block's counts agree with the entries actually present.

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
        errors.append("%s: label `untested` must carry evidence: [] (got %r)" % (where, ev))
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

    for ins in db["instructions"]:
        m = ins["mnemonic"]
        db_names.add(m)
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
        print("  emittable instructions: %d / %d" % (len(emittable), len(db["instructions"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
