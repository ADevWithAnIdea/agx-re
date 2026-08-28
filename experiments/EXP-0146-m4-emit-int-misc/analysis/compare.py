#!/usr/bin/env python3
"""EXP-0146: two-run agreement gate + per-field behaviour map.

  python3 analysis/compare.py run01 run03            # the promotion gate
  python3 analysis/compare.py run01 run03 --extra run02

Writes analysis/field_maps.json (the observed behaviour of every swept field) and prints
the disagreement list that run04 must adjudicate.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import loadruns as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs=2)
    ap.add_argument("--extra", default="")
    ap.add_argument("--out", default=str(HERE / "field_maps.json"))
    args = ap.parse_args()

    A = L.load(args.runs[0])
    B = L.load(args.runs[1])
    widths = L.field_widths()

    keys = [k for k in A["_order"] if k in B]
    only_a = [k for k in A["_order"] if k not in B]
    only_b = [k for k in B["_order"] if k not in A]

    disagree = []
    permap = collections.defaultdict(dict)   # (instr,carrier,field) -> value -> record
    for k in keys:
        ra, rb = A[k], B[k]
        oa, ob = ra["outcome"], rb["outcome"]
        wa, wb = L.words(ra), L.words(rb)
        agreed = (oa == ob) and (wa == wb or oa in ("fault", "hang"))
        instr, carrier, field, val = k
        v = json.loads(val)
        permap[(instr, carrier, field)][val] = {
            "value": v, "outcome": oa if agreed else "DISAGREE",
            "outcome_a": oa, "outcome_b": ob,
            "agreed": agreed,
            "words": list(wa),
            "lut": ra.get("observed", {}).get("lut"),
            "fn": ra.get("observed", {}).get("fn"),
            "delta": ra.get("observed", {}).get("delta"),
            "fault_class": rb.get("observed", {}).get("fault_class"),
            "bytes": ra["bytes"],
        }
        if not agreed:
            disagree.append({"key": list(k), "a": oa, "b": ob,
                             "words_a": list(wa), "words_b": list(wb)})

    out = {"_gate": {"run_a": args.runs[0], "run_b": args.runs[1],
                     "cases_compared": len(keys), "cases_agreed": len(keys) - len(disagree),
                     "cases_disagreed": len(disagree),
                     "only_in_a": len(only_a), "only_in_b": len(only_b)},
           "fields": {}}
    for (instr, carrier, field), vals in sorted(permap.items()):
        oc = collections.Counter(v["outcome"] for v in vals.values())
        ok_vals = sorted(v["value"] for v in vals.values()
                         if v["outcome"] == "ok" and isinstance(v["value"], int))
        dis = [v["value"] for v in vals.values() if v["outcome"] == "DISAGREE"]
        w = widths.get(instr, {}).get(field)
        out["fields"]["%s.%s@%s" % (instr, field, carrier)] = {
            "instr": instr, "field": field, "carrier": carrier,
            "db_width": w, "values_tested": len(vals),
            "full_dense": (w is not None and len(vals) == (1 << w)),
            "outcomes": dict(oc),
            "ok_values": ok_vals,
            "disagreements": sorted(dis) if dis and all(isinstance(x, int) for x in dis) else dis,
        }
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True))
    g = out["_gate"]
    print("GATE %s vs %s: %d cases, %d agreed (%.2f%%), %d disagreed"
          % (g["run_a"], g["run_b"], g["cases_compared"], g["cases_agreed"],
             100.0 * g["cases_agreed"] / max(1, g["cases_compared"]), g["cases_disagreed"]))
    (HERE / "disagreements.json").write_text(json.dumps(disagree, indent=1))
    print("wrote", args.out, "and", HERE / "disagreements.json")


if __name__ == "__main__":
    main()
