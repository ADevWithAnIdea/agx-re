#!/usr/bin/env python3
"""EXP-0184 arm generation -- the SELECTION RULE, frozen in PRE_REGISTRATION.md 7.4.

Reads `raw/prefreeze/census.json` and writes `harness/arms184.json`, which is
then hashed into CAPTURE_CONTRACT.json (amendment) and never edited again.

THE RULE (frozen; a reviewer can check every arm against it):

 1. A carrier that does not EMIT the target instruction is DROPPED, and the drop
    is recorded with its occurrence count. "N carriers tried, 0 occurrences" is a
    bounded negative, not a failure.
 2. Only PARCEL-ALIGNED occurrences are swept. A signature hit at an odd offset
    is recorded in the census as evidence the descriptor signature is ambiguous,
    but is never dispatched as if it were an instruction.
 3. TARGET arms: for each carrier, take occurrences ordered by (baseline field
    value not yet seen in this carrier, then offset), up to MAX_OCC_PER_CARRIER.
    Preferring an unseen baseline value is what makes two arms in one kernel two
    arms: for `if_push.scope` the baseline value IS the nesting parity the field
    is modelled to select, so this is exactly "carriers differ in the dimension
    the field controls".
 4. CONTROL arms (detection power): a field on the SAME instruction, at the SAME
    occurrence, already known to be live, swept over a sampled range. An arm
    whose control never moves is BARRED from supporting any verdict, inert or
    live (EXP-0172 gate rule 3). The controls are:
       copysign          byte+1 (bits 8..15)  -- EXP-0138 (M4): 240/256 silent
                                                 zero, 8 -> -5.0, 8 -> +5.0
       cvt_f2i.dst       bits 24..31          -- EXP-0168 (G17P): hardware-run,
                                                 190/256 moved
       if_push.scope_kind bits 24..31         -- EXP-0140: hardware-run
       rt_query_traverse.opB bits 56..63      -- EXP-M4-14 (A18): {0x42,0x48,0xc8}
                                                 correct, 8 values skip the hit,
                                                 4 HANG
 5. Every arm dispatches its field's FULL encodable range when width <= 8
    (2^width values, dense). Controls are sampled, because a control only has to
    fire once.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import locate184 as L        # noqa: E402

MAX_OCC_PER_CARRIER = {"cs": 1, "cvt": 1, "cf": 10, "rq": 14}
TARGET_FIELD = {"copysign": "operands", "cvt_f2i": "b9", "if_push": "scope",
                "rt_query_traverse": "dst"}

# (field label, start, width, values, note)
CONTROLS = {
    "copysign": [("_b1_match", 8, 8, list(range(256)),
                  "db.json models byte+1 as a FIXED MATCH CONSTANT (0xc2); "
                  "EXP-0138 (M4) measured it LIVE. Detection-power control AND "
                  "the G17P half of a db defect.")],
    "cvt_f2i": [("dst", 24, 8, list(range(0, 256, 8)),
                 "hardware-run on G17P (EXP-0168, 190/256 moved) -- must move "
                 "here or this arm has no detection power")],
    "if_push": [("scope_kind", 24, 8, [0, 1, 2, 4, 5, 8, 16, 26, 32, 33, 37,
                                       64, 128, 160, 224, 255],
                 "hardware-run (EXP-0140); 0x01 vs 0x1a change the region KIND "
                 "and 0x01 masks off the only lane of a 1-thread dispatch "
                 "(EXP-0179) -- must move on a 32-lane dispatch")],
    "rt_query_traverse": [("opB", 56, 8, [0x00, 0x02, 0x06, 0x07, 0x0a, 0x0f,
                                          0x1a, 0x20, 0x40, 0x42, 0x48, 0x50,
                                          0x60, 0xc8, 0xff],
                           "hardware-run on A18 (EXP-M4-14): {0x42,0x48,0xc8} "
                           "correct, eight values skip the near hit, four HANG")],
}
EXTRA_TARGETS = {
    # copysign byte+2 is also modelled as a fixed match constant; EXP-0138 (M4)
    # measured it a 256/256 don't-care. Swept on ONE carrier for the G17P record.
    "copysign": [("_b2_match", 16, 8, list(range(256)), "cs_load")],
}


def main():
    census = json.loads((EXP / "raw" / "prefreeze" / "census.json").read_text())
    arms, dropped = [], []
    for name, rec in sorted(census.items()):
        mn = rec["mnemonic"]
        group = rec["group"]
        if rec.get("error"):
            dropped.append({"carrier": name, "reason": "compile_fail",
                            "detail": rec["error"][:200]})
            continue
        occ = [h for h in rec.get("occurrences", []) if h["parcel_aligned"]]
        if not occ:
            dropped.append({"carrier": name, "reason": "no_occurrence",
                            "n_signature_hits": rec.get("n_occ", 0),
                            "n_aligned": 0})
            continue
        fld = TARGET_FIELD[mn]
        start, width = L.field_span(mn, fld)
        seen, chosen = set(), []
        for h in sorted(occ, key=lambda h: (h["baseline_field"] in seen, h["off"])):
            chosen.append(h)
            seen.add(h["baseline_field"])
            if len(chosen) >= MAX_OCC_PER_CARRIER[group]:
                break
        for i, h in enumerate(chosen):
            arms.append({
                "group": group, "carrier": name, "instr": mn, "field": fld,
                "arm": "%s#%d/%s.%s" % (name, i, mn, fld),
                "occ": i, "off": h["off"], "len": h["len"],
                "start": start, "width": width,
                "values": list(range(1 << width)),
                "baseline_field": h["baseline_field"],
                "baseline_bytes": h["bytes"], "role": "target",
                "note": "target field, dense full range",
            })
            for (cf, cs_, cw, cv, cnote) in CONTROLS.get(mn, []):
                arms.append({
                    "group": group, "carrier": name, "instr": mn, "field": cf,
                    "arm": "%s#%d/%s.%s" % (name, i, mn, cf),
                    "occ": i, "off": h["off"], "len": h["len"],
                    "start": cs_, "width": cw, "values": cv,
                    "baseline_field": h["baseline_field"],
                    "baseline_bytes": h["bytes"], "role": "control",
                    "note": cnote,
                })
            if i == 0:
                for (xf, xs, xw, xv, only) in EXTRA_TARGETS.get(mn, []):
                    if only and only != name:
                        continue
                    arms.append({
                        "group": group, "carrier": name, "instr": mn,
                        "field": xf, "arm": "%s#%d/%s.%s" % (name, i, mn, xf),
                        "occ": i, "off": h["off"], "len": h["len"],
                        "start": xs, "width": xw, "values": xv,
                        "baseline_field": h["baseline_field"],
                        "baseline_bytes": h["bytes"], "role": "target",
                        "note": "modelled as a fixed match constant; swept for "
                                "the G17P record",
                    })
    doc = {"generated_from": "raw/prefreeze/census.json",
           "rule": "analysis/gen_arms.py docstring (frozen in "
                   "PRE_REGISTRATION.md section 7.4)",
           "max_occ_per_carrier": MAX_OCC_PER_CARRIER,
           "dropped_carriers": dropped, "arms": arms}
    p = EXP / "harness" / "arms184.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    n = sum(len(a["values"]) for a in arms)
    print("arms=%d cases=%d dropped=%d -> %s" % (len(arms), n, len(dropped), p))
    for d in dropped:
        print("  DROPPED %s: %s" % (d["carrier"], d["reason"]))
    for a in arms:
        print("  %-34s %-8s off=%-6d start=%-3d w=%d n=%d"
              % (a["arm"], a["role"], a["off"], a["start"], a["width"],
                 len(a["values"])))


if __name__ == "__main__":
    main()
