#!/usr/bin/env python3
"""EXP-0171 -- what these verdicts would close, computed WITHOUT editing
`tools/agx-isa/validation.json` (the orchestrator owns it).

Overlays `analysis/field_verdicts_flat.json` on the pinned `work/frozen/
validation.json` and recounts, per instruction, how many fields are below
emitter grade (`hardware-run` or `isolated-byte-diff`) before and after.

Two overlays are reported separately, because they are not equally strong:
  * MOVEMENT-ONLY -- apply only rows whose promotion rests on the field MOVING
    (label `hardware-run`). This is the conservative number.
  * FULL          -- also apply the rows promoted FROM PROVEN INERTNESS to
    `isolated-byte-diff`. Those are flagged so an adversarial re-audit knows
    exactly which closures depend on them.

  python3 analysis/closure.py
"""
from __future__ import print_function

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
GRADE = ("hardware-run", "isolated-byte-diff")

db = dict((i["mnemonic"], i) for i in
          json.loads((EXP / "work" / "frozen" / "db.json").read_text())["instructions"])
val = json.loads((EXP / "work" / "frozen" / "validation.json").read_text())["instructions"]
new = json.loads((HERE / "field_verdicts_flat.json").read_text())
full = json.loads((HERE / "field_verdicts.json").read_text())["verdicts"]


def blocking(mn, overlay):
    d = db[mn]
    out = []
    for f in d["fields"]:
        key = "%s.%s" % (mn, f["name"])
        lab = overlay.get(key) or val.get(mn, {}).get(f["name"], {}).get("label")
        if lab not in GRADE:
            out.append((f["name"], lab))
    return out


mv_overlay = dict((k, v["label"]) for k, v in new.items()
                  if v["label"] == "hardware-run")
full_overlay = dict((k, v["label"]) for k, v in new.items()
                    if v["label"] in GRADE)
from_inert = sorted(k for k, v in full.items()
                    if v["label"] == "isolated-byte-diff"
                    and "DENSE-INERT" in v.get("note", ""))

rows = []
for mn in sorted(set(k.split(".", 1)[0] for k in new)):
    b0 = blocking(mn, {})
    b1 = blocking(mn, mv_overlay)
    b2 = blocking(mn, full_overlay)
    rows.append((mn, len(b0), len(b1), len(b2), b2))

print("%-16s %8s %10s %8s  remaining" % ("instruction", "before", "movement",
                                         "full"))
closed_mv, closed_full = [], []
for mn, n0, n1, n2, rem in rows:
    print("%-16s %8d %10d %8d  %s" % (mn, n0, n1, n2,
                                      ", ".join("%s(%s)" % r for r in rem)))
    if n0 > 0 and n1 == 0:
        closed_mv.append(mn)
    elif n0 > 0 and n2 == 0:
        closed_full.append(mn)

report = {
    "closed_on_movement_evidence": closed_mv,
    "closed_only_with_a_promotion_from_proven_inertness": closed_full,
    "rows_promoted_from_proven_inertness": from_inert,
    "per_instruction": [{"instruction": r[0], "blocking_before": r[1],
                         "blocking_after_movement_only": r[2],
                         "blocking_after_full": r[3],
                         "still_blocking": [{"field": x[0], "label": x[1]}
                                            for x in r[4]]} for r in rows],
    "_note": "computed against the PINNED work/frozen/validation.json; the live "
             "repo copy is the orchestrator's and is not edited here.",
}
(HERE / "closure.json").write_text(json.dumps(report, indent=1, sort_keys=True))
print()
print("CLOSED on movement evidence alone :", closed_mv)
print("CLOSED only with an inertness promotion:", closed_full)
print("rows promoted from proven inertness:", from_inert)
