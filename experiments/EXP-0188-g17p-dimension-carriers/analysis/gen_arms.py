#!/usr/bin/env python3
"""EXP-0188 arm generation -- the SELECTION RULE, frozen in PRE_REGISTRATION.md 7.4.

Reads `raw/prefreeze/census.json` and writes `harness/arms188.json`, which is then
hashed into CAPTURE_CONTRACT.json (amendment) and never edited again.

THE RULE (frozen; a reviewer can check every arm against it):

 1. A carrier that does not EMIT the target instruction is DROPPED, and the drop
    is recorded with its occurrence count. "N carriers tried, 0 occurrences" is a
    bounded negative, not a failure. It is never repaired after the fact.
 2. Only PARCEL-ALIGNED occurrences are swept. A signature hit at an odd offset
    is recorded in the census as evidence the descriptor signature is ambiguous,
    but is never dispatched as if it were an instruction.
 3. TARGET arms: occurrences are ordered so that the DIMENSION spreads FIRST --
    an occurrence whose `occ_dimension_fields` value has not been seen yet in
    this carrier is taken before any repeat, then an unseen baseline value of the
    target field, then by offset. For `if_push` the dimension field is
    `scope_kind`, so a loop-iteration (0x1a) push is always preferred over a
    fifth conditional-skip (0x01) push. This is the whole point of the
    experiment: eight arms that cannot express a field are one arm.
 4. CONTROL arms (detection power): a field on the SAME instruction, at the SAME
    occurrence, already known live, swept over a sampled range. An arm at an
    occurrence where NO control moved is BARRED from supporting any verdict,
    inert OR live.
 5. Every target arm dispatches its field's FULL encodable range when width <= 8
    (2^width values, dense). Controls are sampled: a control only has to fire once.
 6. NO ABORT PATH and no hang budget anywhere (protocol 3c).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import locate188 as L        # noqa: E402
import targets188 as T       # noqa: E402


def main():
    census = json.loads((EXP / "raw" / "prefreeze" / "census.json").read_text())
    arms, dropped = [], []
    for tgt in T.TARGETS:
        mn, fld, group = tgt["mnemonic"], tgt["field"], tgt["group"]
        dimflds = tgt.get("occ_dimension_fields", [])
        start, width = L.field_span(mn, fld)
        for name in tgt["carriers"]:
            rec = census.get("%s/%s" % (group, name))
            if rec is None or rec.get("error"):
                dropped.append({"group": group, "carrier": name,
                                "reason": "compile_fail",
                                "detail": (rec or {}).get("error", "absent")[:200]})
                continue
            occ = [h for h in rec.get("occurrences", []) if h["parcel_aligned"]]
            if not occ:
                dropped.append({"group": group, "carrier": name,
                                "reason": "no_occurrence",
                                "n_signature_hits": rec.get("n_occ", 0),
                                "dimension_value": rec.get("dimension_value")})
                continue
            seen_dim, seen_base, chosen = set(), set(), []
            pool = list(occ)
            while pool and len(chosen) < tgt["max_occ_per_carrier"]:
                pool.sort(key=lambda h: (
                    tuple(h.get("dim_" + d) for d in dimflds) in seen_dim,
                    h["baseline_field"] in seen_base,
                    h["off"]))
                h = pool.pop(0)
                chosen.append(h)
                seen_dim.add(tuple(h.get("dim_" + d) for d in dimflds))
                seen_base.add(h["baseline_field"])
            for i, h in enumerate(chosen):
                dimv = {d: h.get("dim_" + d) for d in dimflds}
                arms.append({
                    "group": group, "carrier": name, "instr": mn, "field": fld,
                    "arm": "%s/%s#%d/%s.%s" % (group, name, i, mn, fld),
                    "occ": i, "off": h["off"], "len": h["len"],
                    "start": start, "width": width,
                    "values": list(range(1 << width)),
                    "baseline_field": h["baseline_field"],
                    "baseline_bytes": h["bytes"], "role": "target",
                    "carrier_dimension": rec.get("dimension_value"),
                    "occ_dimension": dimv,
                    "note": "target field, dense full range",
                })
                for (cf, cv, cnote) in T.CONTROLS.get(mn, []):
                    cs_, cw = L.field_span(mn, cf)
                    arms.append({
                        "group": group, "carrier": name, "instr": mn,
                        "field": cf,
                        "arm": "%s/%s#%d/%s.%s" % (group, name, i, mn, cf),
                        "occ": i, "off": h["off"], "len": h["len"],
                        "start": cs_, "width": cw,
                        "values": [v for v in cv if v < (1 << cw)],
                        "baseline_field": h["baseline_field"],
                        "baseline_bytes": h["bytes"], "role": "control",
                        "carrier_dimension": rec.get("dimension_value"),
                        "occ_dimension": dimv, "note": cnote,
                    })
    doc = {"generated_from": "raw/prefreeze/census.json",
           "rule": "analysis/gen_arms.py docstring (frozen in "
                   "PRE_REGISTRATION.md section 7.4)",
           "dropped_carriers": dropped, "arms": arms}
    p = EXP / "harness" / "arms188.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    n = sum(len(a["values"]) for a in arms)
    print("arms=%d cases=%d dropped=%d -> %s" % (len(arms), n, len(dropped), p))
    for d in dropped:
        print("  DROPPED %s/%s: %s" % (d["group"], d["carrier"], d["reason"]))
    for a in arms:
        print("  %-38s %-8s off=%-6d start=%-3d w=%d n=%-4d %s"
              % (a["arm"], a["role"], a["off"], a["start"], a["width"],
                 len(a["values"]), a["occ_dimension"]))


if __name__ == "__main__":
    main()
