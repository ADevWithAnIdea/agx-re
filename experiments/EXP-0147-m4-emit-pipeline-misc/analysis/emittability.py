#!/usr/bin/env python3
"""Which of the ten instructions are EMITTABLE after this experiment?

An instruction qualifies only if EVERY field in its db.json descriptor is
hardware-run or isolated-byte-diff (docs/evidence-classification.md section 2).
Combines the committed tools/agx-isa/validation.json labels with this
experiment's analysis/field_verdicts.json. Read-only; edits nothing.
"""
import json, os

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
GOOD = ("hardware-run", "isolated-byte-diff")
TARGETS = ["tile_read", "tile_read_mrt", "vtx_coord_xform", "vtx_out_pos", "pixel_order",
           "mesh_out_src", "matrix_mac", "scoreboard_fence", "compute_fence_scoped",
           "n3_sample_read"]


def main():
    db = {i["mnemonic"]: i for i in json.load(open(os.path.join(REPO, "tools/agx-isa/db.json")))["instructions"]}
    val = json.load(open(os.path.join(REPO, "tools/agx-isa/validation.json")))["instructions"]
    new = json.load(open(os.path.join(EXP, "analysis/field_verdicts.json")))["fields"]

    rows, summary = [], {"emittable_after": [], "still_blocked": []}
    for m in TARGETS:
        fields = [f["name"] for f in db[m].get("fields", [])]
        before_bad, after_bad, promoted = [], [], []
        for fn in fields:
            old = val.get(m, {}).get(fn, {}).get("label", "untested")
            nl = new.get(f"{m}.{fn}", {}).get("label")
            eff = nl or old
            if old not in GOOD: before_bad.append(fn)
            if eff not in GOOD: after_bad.append(f"{fn}({eff})")
            if old not in GOOD and eff in GOOD: promoted.append(fn)
        rows.append({"instruction": m, "n_fields": len(fields),
                     "blocking_before": before_bad, "blocking_after": after_bad,
                     "promoted_here": promoted,
                     "emittable_after": not after_bad})
        (summary["emittable_after"] if not after_bad else summary["still_blocked"]).append(m)

    out = {"_note": "read-only projection; db.json/validation.json unchanged by this experiment",
           "per_instruction": rows, "summary": summary,
           "fields_promoted_total": sum(len(r["promoted_here"]) for r in rows)}
    p = os.path.join(EXP, "analysis", "emittability.json")
    with open(p, "w") as f: json.dump(out, f, indent=2); f.write("\n")
    for r in rows:
        mark = "EMITTABLE" if r["emittable_after"] else "blocked"
        print(f"{r['instruction']:22s} {mark:10s} promoted={len(r['promoted_here'])}/{len(r['blocking_before'])}"
              f"  still={r['blocking_after']}")
    print("\nfields promoted:", out["fields_promoted_total"])


if __name__ == "__main__":
    main()
