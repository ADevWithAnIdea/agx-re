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
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAL = os.path.join(ROOT, "tools", "agx-isa", "validation.json")
DB = os.path.join(ROOT, "tools", "agx-isa", "db.json")

LABELS = ["hardware-run", "isolated-byte-diff", "corpus-correlation",
          "tokenization-only", "single-template-inference", "api-accept-reject",
          "host-private", "untested"]
STRENGTH = {l: i for i, l in enumerate(LABELS)}   # lower index == stronger
EMIT_OK = {"hardware-run", "isolated-byte-diff"}


def load_db_fields():
    db = json.load(open(DB))
    return {i["mnemonic"]: [f["name"] for f in i.get("fields", [])]
            for i in db["instructions"]}


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
        if "EMITTABLE VETO" in (entry.get("_instruction") or {}).get("note", ""):
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
            lab = v.get("label")
            if lab not in STRENGTH:
                problems.append("%s: %s has invalid label %r" % (src, key, lab)); continue
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
            val["instructions"][m][f] = {k: v[k] for k in
                                         ("label", "range", "target", "evidence", "note")
                                         if k in v}
            applied += 1

    if problems:
        print("PROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  -", p)

    cov = recompute_coverage(val, dbf)
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
