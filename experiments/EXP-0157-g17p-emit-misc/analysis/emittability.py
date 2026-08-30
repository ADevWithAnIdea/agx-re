#!/usr/bin/env python3
"""EXP-0157: which dispatched descriptors become EMITTABLE?

`docs/evidence-classification.md` (the `emittable` rule): a family may be called
emittable only if EVERY field an emitter must fill is `hardware-run` or
`isolated-byte-diff`. This script applies that rule mechanically against
(a) this experiment's verdicts and (b) whatever `validation.json` already holds,
so no descriptor is claimed emittable by hand.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GOOD = {"hardware-run", "isolated-byte-diff"}
TARGETS = ("n2_op6 n2_op8 n2_op10 n3_mov coord_madf sr_read_wide h_coord_hi "
           "h_coord_hi_ext mesh_out_src op04_len8 scoreboard_fence "
           "compute_fence_scoped rtq_pred sfu_marker rtq_dualsrc rtq_state_move "
           "ray_move ray_move_copy6 ray_move_zero6 ray_move_zinit").split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdicts", default=str(HERE / "field_verdicts_by_carrier.json"))
    ap.add_argument("--out", default=str(HERE / "emittability.json"))
    a = ap.parse_args()
    db = json.load(open(REPO / "tools" / "agx-isa" / "db.json"))
    val = json.load(open(REPO / "tools" / "agx-isa" / "validation.json"))["instructions"]
    mine = json.load(open(a.verdicts))
    fields = {i["mnemonic"]: [f["name"] for f in i["fields"]] for i in db["instructions"]}

    ftype = {i["mnemonic"]: {f["name"]: f.get("type") for f in i["fields"]}
             for i in db["instructions"]}
    best = collections.defaultdict(dict)     # instr -> field -> (label, source)
    pinned = collections.defaultdict(dict)   # instr -> field -> ok_values
    for name, e in mine.items():
        if name in ("db_defects", "_gates"):
            continue
        head = name.split("@")[0]
        instr, _, fld = head.partition(".")
        if not fld or "." in fld:
            continue
        cur = best[instr].get(fld)
        if cur is None or (e["label"] in GOOD and cur[0] not in GOOD):
            best[instr][fld] = (e["label"], "EXP-0157/" + e.get("carrier", "?"))
        # A field whose ONLY accepted value is the one the compiler already
        # chose is `hardware-run` (it was densely swept and the rule is exact)
        # but it does NOT let an emitter choose an operand. Report it, never
        # hide it behind the label.
        # "pinned" = this evidence does NOT let an emitter choose the operand:
        # either no swept value at all reproduced the oracle, or the exact rule
        # leaves no free bit (the accepted set is the compiler's own value, up
        # to bits that are don't-care). Such a field is legitimately
        # `hardware-run` -- it was densely swept and its rule is exact -- but
        # reporting the descriptor as "emittable" without saying so would
        # mislead, so it is surfaced separately and never hidden by the label.
        n = e.get("ok_values")
        r = e.get("exact_rule")
        free = None
        if r:
            try:
                free = int(r.split("&")[1].split(")")[0].strip(), 16)
            except Exception:
                free = None
        isp = (n == 0) or (n is not None and n <= 1 and free == 0xFF)
        prev = pinned[instr].get(fld)
        pinned[instr][fld] = isp if prev is None else (prev and isp)
    report = {}
    for m in TARGETS:
        flds = fields.get(m, [])
        rows = {}
        for f in flds:
            lab, src = best.get(m, {}).get(f, (None, None))
            if lab is None:
                lab = (val.get(m, {}).get(f) or {}).get("label", "untested")
                src = "validation.json"
            rows[f] = {"label": lab, "source": src}
        emittable = bool(flds) and all(v["label"] in GOOD for v in rows.values())
        pin = sorted(f for f in flds
                     if pinned.get(m, {}).get(f) is True
                     and ftype.get(m, {}).get(f) in ("reg", "opcode", "enum", "imm"))
        report[m] = {"n_fields": len(flds), "emittable": emittable,
                     "blocking": sorted(f for f, v in rows.items()
                                        if v["label"] not in GOOD),
                     "single_value_only": pin,
                     "operand_choice_available": emittable and not pin,
                     "fields": rows}
    Path(a.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    for m in TARGETS:
        r = report[m]
        print("%-22s fields=%-2d %-14s pinned:%-22s blocking: %s"
              % (m, r["n_fields"], "EMITTABLE" if r["emittable"] else
                 ("NO FIELDS" if not r["n_fields"] else "not yet"),
                 ",".join(r["single_value_only"]) or "-",
                 ", ".join(r["blocking"]) or "-"))


if __name__ == "__main__":
    main()
