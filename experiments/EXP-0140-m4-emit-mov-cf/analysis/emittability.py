#!/usr/bin/env python3
"""EXP-0140: how many instructions did this experiment actually make EMITTABLE?

Reads tools/agx-isa/{db.json,validation.json} (READ-ONLY) plus this
experiment's analysis/field_verdicts.json, and reports, per instruction in the
two dispatched families, which fields an emitter must fill, what label each
carries before and after this experiment, and whether the instruction clears
the `emittable` rule from docs/evidence-classification.md §2:

    a family may be described as emittable only if EVERY field an emitter must
    fill is `hardware-run` or `isolated-byte-diff`.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]

MOV = ["get_sr", "mov_imm", "psel", "reg_move_c0", "reg_move_c1", "reg_move_c2var",
       "reg_move_c9", "reg_move_cb", "sel", "uniform_mov"]
CF = ["call", "call_indirect", "frame_prologue", "if_push", "if_push_pred", "jump",
      "jump_cond", "link_save_restore", "mask_op", "pop_reconverge", "ret", "ret_luse",
      "stop"]
GOOD = ("hardware-run", "isolated-byte-diff")


def main():
    db = json.load(open(REPO / "tools/agx-isa/db.json"))
    val = json.load(open(REPO / "tools/agx-isa/validation.json"))
    vi = val.get("instructions", val)
    new = json.load(open(HERE / "field_verdicts.json"))["fields"]
    ins = {e["mnemonic"]: e for e in db["instructions"]}

    report, totals = {}, {"before": 0, "after": 0, "fields_lifted": 0}
    for fam, names in (("MOV", MOV), ("CF", CF)):
        for m in names:
            e = ins.get(m)
            if not e:
                continue
            rows = []
            for f in e["fields"]:
                key = "%s.%s" % (m, f["name"])
                old = (vi.get(m, {}).get(f["name"], {}) or {}).get("label", "untested")
                nl = new.get(key, {}).get("label")
                rows.append({"field": f["name"], "before": old, "after": nl or old,
                              "lifted": bool(nl in GOOD and old not in GOOD)})
            before_ok = all(r["before"] in GOOD for r in rows)
            after_ok = all(r["after"] in GOOD for r in rows)
            totals["before"] += before_ok
            totals["after"] += after_ok
            totals["fields_lifted"] += sum(r["lifted"] for r in rows)
            report[m] = {"family": fam, "fields": rows,
                          "emittable_before": before_ok, "emittable_after": after_ok,
                          "blocking_after": [r["field"] for r in rows if r["after"] not in GOOD]}
    out = {"totals": totals, "instructions": report,
           "newly_emittable": sorted(m for m, r in report.items()
                                      if r["emittable_after"] and not r["emittable_before"])}
    (HERE / "emittability.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("emittable before: %d / %d" % (totals["before"], len(report)))
    print("emittable after : %d / %d" % (totals["after"], len(report)))
    print("fields lifted to emitter grade: %d" % totals["fields_lifted"])
    print("newly emittable:", ", ".join(out["newly_emittable"]) or "(none)")
    for m, r in sorted(report.items()):
        if not r["emittable_after"]:
            print("  still blocked: %-16s %s" % (m, r["blocking_after"]))


if __name__ == "__main__":
    main()
