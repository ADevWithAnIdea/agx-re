#!/usr/bin/env python3
"""Merge agents' analysis/field_verdicts.json into tools/agx-isa/validation.json.

Orchestrator-only. Agents never write validation.json; they emit verdicts in the
schema fixed by experiments/FIELD-SWEEP-PROTOCOL.md 5 and this script merges them.

Refuses to weaken a label without --allow-downgrade: if an agent reports a field
as `untested` that is already `hardware-run`, that is either a real refutation
(which deserves a human decision and a PROVENANCE row) or a bug in the agent's
verdict file. Silently taking the weaker label would quietly delete evidence;
silently taking the stronger one would hide a refutation. So it stops.

  python3 work/merge_verdicts.py --dry-run experiments/EXP-01*/analysis/field_verdicts.json
  python3 work/merge_verdicts.py          experiments/EXP-01*/analysis/field_verdicts.json
"""
import argparse, hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAL = os.path.join(ROOT, "tools", "agx-isa", "validation.json")
DB = os.path.join(ROOT, "tools", "agx-isa", "db.json")

LABELS = ["hardware-run", "isolated-byte-diff", "corpus-correlation",
          "tokenization-only", "single-template-inference", "api-accept-reject",
          "host-private", "untested"]
STRENGTH = {l: i for i, l in enumerate(LABELS)}   # lower index == stronger
EMIT_OK = {"hardware-run", "isolated-byte-diff"}
DATA_WORD_ROLE = "data-word"


def load_db_fields():
    db = json.load(open(DB))
    return {i["mnemonic"]: [f["name"] for f in i.get("fields", [])]
            for i in db["instructions"]}


def load_db_spans():
    """(mnemonic, field) -> (start, width), so a verdict that records the bits it
    measured can be checked against where db.json now puts that name."""
    db = json.load(open(DB))
    return {(i["mnemonic"], f["name"]): (f["start"], f["width"])
            for i in db["instructions"] for f in i.get("fields", [])}


def recompute_coverage(val, dbf):
    counts = {l: 0 for l in LABELS}
    total = 0
    for m, entry in val["instructions"].items():
        for n in dbf.get(m, []):
            if n in entry:
                counts[entry[n]["label"]] += 1
                total += 1
    emittable = []
    for m, entry in val["instructions"].items():
        names = dbf.get(m, [])
        labs = [entry[n]["label"] for n in names if n in entry]
        ok = bool(names) and len(labs) == len(names) and all(l in EMIT_OK for l in labs)
        inst = entry.get("_instruction") or {}
        if "EMITTABLE VETO" in inst.get("note", ""):
            ok = False
        # DEF-0173-1, gated 2026-08-30 after EXP-0181 refreshed the labels from evidence.
        # The rule used to read only FIELD labels, so an instruction could be "emittable"
        # while the DESCRIPTOR itself was only corpus-correlated. That was left ungated
        # while the labels were stale -- `mov_imm` is proven end-to-end and still read
        # `corpus-correlation`. EXP-0181 checked all 30: every one had been DISPATCHED on
        # hardware (230,804 raw cases over 18 experiments), so the stale labels were
        # factually wrong for 28 of them. With the labels corrected the gate costs FIVE
        # instructions, each for a named reason -- e.g. `frag_depth_store`, whose depth
        # output has never been read back because its sweeps were scored against a COLOUR
        # probe, and `vary_slot`, whose documented role DEF-0172-3 refuted outright.
        if inst.get("label") not in EMIT_OK:
            ok = False
        if ok:
            emittable.append(m)
    emittable.sort()
    cov = val["coverage"]
    cov["total_fields"] = total
    cov["by_label"] = counts
    cov["by_label_pct"] = {l: round(100.0 * counts[l] / total, 1) for l in LABELS}
    cov["emittable_instructions"] = len(emittable)
    cov["emittable_mnemonics"] = emittable
    cov["decodable_not_yet_emittable"] = len(val["instructions"]) - len(emittable)

    # The corrected metric (EXP-0148): six of the scaffolding descriptors are data
    # words by their own committed semantics, so they are not instructions an
    # emitter emits and must not sit in the denominator. validate_labels.py
    # recomputes these independently and FAILS if we leave them stale -- which is
    # exactly what happened after the EXP-0155 merge, so recompute them here too.
    db = json.load(open(DB))
    dw = sorted(i["mnemonic"] for i in db["instructions"]
                if i.get("emitter_role") == DATA_WORD_ROLE)
    rel = [i["mnemonic"] for i in db["instructions"]
           if i.get("emitter_role") != DATA_WORD_ROLE]
    cov["data_word_descriptors"] = len(dw)
    cov["data_word_mnemonics"] = dw
    cov["emitter_relevant_instructions"] = len(rel)
    cov["emittable_of_emitter_relevant"] = len([m for m in emittable if m not in set(dw)])
    return cov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("verdicts", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-downgrade", action="store_true",
                    help="accept a weaker label than the one already recorded")
    a = ap.parse_args()

    val = json.load(open(VAL))
    dbf = load_db_fields()
    dbspan = load_db_spans()
    db_sha = hashlib.sha256(open(DB,"rb").read()).hexdigest()
    before = dict(val["coverage"]["by_label"])
    before_emit = val["coverage"]["emittable_instructions"]

    applied = skipped = 0
    problems = []
    for path in a.verdicts:
        if not os.path.exists(path):
            problems.append("missing verdict file: %s" % path); continue
        doc = json.load(open(path))
        src = os.path.basename(os.path.dirname(os.path.dirname(path)))
        for key, v in doc.items():
            if key == "db_defects":
                continue                       # applied to db.json by hand
            if "." not in key:
                problems.append("%s: key %r is not <mnemonic>.<field>" % (src, key)); continue
            m, f = key.split(".", 1)
            if m not in val["instructions"]:
                problems.append("%s: unknown mnemonic %s" % (src, m)); continue
            if f not in dbf.get(m, []):
                problems.append("%s: %s is not a field of %s in db.json" % (src, f, m)); continue
            # DEF-0166-2 (EXP-0166, 2026-08-30): if the verdict names the bits it
            # measured, refuse it when db.json has since moved that field. Names get
            # REUSED across a descriptor repair -- EXP-0161 renamed carry_gen's
            # `subop` -> `srcA` and `srcA` -> `srcB`, so a name-keyed merge of
            # EXP-0146's older rows would have silently attached each verdict to the
            # WRONG BYTE while every existing check passed. A verdict is a claim about
            # bits; the name is only a handle for them.
            want = dbspan.get((m, f))
            got = (v.get("start"), v.get("width"))
            # DEF-0212-1 (EXP-0212): the guard below only fires when the verdict
            # NAMES the bits it measured. A verdict that omits start/width skipped
            # it entirely -- `sfu_marker.b0_hi` had its span moved (3,5)->(5,3) and
            # would have passed silently. The guard was only as strong as the
            # verdict's honesty about which bits it measured. So: if db.json knows
            # the span and the verdict does not state one, REFUSE. Stating the bits
            # you measured is cheap; attaching a verdict to the wrong byte is not.
            if got == (None, None) and want:
                problems.append(
                    "%s: %s states no start/width, but db.json has start=%s width=%s. "
                    "A verdict is a claim about BITS; the name is only a handle for them, "
                    "and names get reused across a descriptor repair. Re-emit the verdict "
                    "with the bits it actually measured." % (src, key, want[0], want[1]))
                continue
            if got != (None, None) and want and got != want:
                problems.append(
                    "%s: %s claims bits start=%s width=%s but db.json now has start=%s "
                    "width=%s -- the descriptor moved under this verdict; re-derive it "
                    "rather than merging by name" % (src, key, got[0], got[1], want[0], want[1]))
                continue
            lab = v.get("label")
            if lab not in STRENGTH:
                problems.append("%s: %s has invalid label %r" % (src, key, lab)); continue
            # DEF-0214-1: the gates checked whether `evidence` was EMPTY but never
            # what TYPE it was. EXP-0214 emitted a prose locator string
            # ("EXP-0203 (raw/g17p_run21,22,... field `ext` byte_index 5)") where the
            # schema takes a list of experiment IDs; this merged 13 rows clean and
            # validate_labels.py failed on all of them afterwards. A string is also
            # truthy, so the emptiness check above passed it through. Locator prose is
            # useful -- it belongs in `note`.
            ev = v.get("evidence")
            if ev is not None and not isinstance(ev, list):
                problems.append(
                    "%s: %s has evidence of type %s, not a list. `evidence` takes "
                    "experiment IDs (e.g. [\"EXP-0203\"]); put locator prose in `note`."
                    % (src, key, type(ev).__name__)); continue
            if isinstance(ev, list) and any(not isinstance(x, str) or not x.strip()
                                            for x in ev):
                problems.append("%s: %s has a non-string or empty entry in `evidence`"
                                % (src, key)); continue
            if lab != "untested" and not v.get("evidence"):
                problems.append("%s: %s is %s with empty evidence" % (src, key, lab)); continue
            if lab == "hardware-run" and v.get("range") in (None, "", "tested"):
                problems.append("%s: %s is hardware-run without a real range" % (src, key)); continue
            cur = val["instructions"][m].get(f)
            if cur and STRENGTH[lab] > STRENGTH[cur["label"]] and not a.allow_downgrade:
                problems.append("%s: %s would WEAKEN %s -> %s; rerun with --allow-downgrade "
                                "only after deciding whether this is a real refutation"
                                % (src, key, cur["label"], lab))
                skipped += 1
                continue
            # `range` is free prose, so no tool can check COVERAGE -- a field can
            # clear every gate we have on two dispatched values, because neither the
            # merge policy nor EXP-0164's `stable_live` has a coverage term (EXP-0169
            # found this in EXP-0164's gate; it applies equally here). Carry the
            # machine-readable counts through whenever a verdict supplies them, so the
            # question becomes answerable. `distinct_bytes` is the one that matters:
            # DEF-0166-1 showed a sweep can dispatch 256 values while the hardware sees
            # 8 distinct encodings, and only the byte count reveals that.
            val["instructions"][m][f] = {k: v[k] for k in
                                         ("label", "range", "target", "evidence", "note",
                                          "values_dispatched", "distinct_bytes",
                                          "encodable_range", "start", "width")
                                         if k in v}
            applied += 1

    if problems:
        print("PROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  -", p)

    cov = recompute_coverage(val, dbf)
    val["db_sha256"] = db_sha   # keep the pin honest; a stale hash means stale labels
    print("\napplied %d field verdicts, skipped %d" % (applied, skipped))
    print("emitter-grade: %d -> %d fields" % (
        before.get("hardware-run", 0) + before.get("isolated-byte-diff", 0),
        cov["by_label"]["hardware-run"] + cov["by_label"]["isolated-byte-diff"]))
    print("emittable instructions: %d -> %d" % (before_emit, cov["emittable_instructions"]))
    print("  now emittable:", ", ".join(cov["emittable_mnemonics"]) or "(none)")

    if a.dry_run:
        print("\n--dry-run: validation.json NOT written")
        return 0 if not problems else 1

    json.dump(val, open(VAL, "w"), indent=1)
    print("\nwrote", VAL)
    for cmd in (["python3", os.path.join(ROOT, "tools/agx-isa/validate_labels.py")],
                ["python3", os.path.join(ROOT, "tools/agx-isa/roundtrip_test.py")]):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        tail = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
        print("%-24s rc=%d  %s" % (os.path.basename(cmd[1]), r.returncode, tail))
        if r.returncode != 0:
            return 1
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
