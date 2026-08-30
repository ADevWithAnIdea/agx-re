#!/usr/bin/env python3
"""EXP-0171 -- the coverage gate. Counts DISTINCT `bytes`, never dispatches.

`isadb.assemble()` ORs the match constant before the field values and an OR
cannot clear a bit, so 53 fields in db.json were silently under-swept while
reporting full coverage (EXP-0166 DEF-0166-1, fixed 4b16d0b4; `irotate.b2`
reached 32 of 256 encodings while reporting 256). This experiment splices RAW
BYTES and never routes a swept value through `assemble()`, and this script is
the proof: for every (arm, carrier, byte) it counts the number of DISTINCT
`bytes` strings actually recorded in `raw/`, and compares it against 256.

  python3 analysis/coverage.py raw/g17p_20260830_run01 [more run dirs...]

CLEAN-ROOM: reads only our own append-only JSONL evidence.
"""
from __future__ import print_function

import json
import sys
from collections import defaultdict
from pathlib import Path


def load(rundir):
    p = Path(rundir) / "sweep.jsonl"
    out = []
    for ln in p.open():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def main():
    runs = sys.argv[1:]
    if not runs:
        print(__doc__)
        return 2
    report = {"runs": {}, "under_covered": [], "spec": "distinct `bytes` "
              "strings recorded in raw/, not the dispatched-value count"}
    bad = 0
    for rd in runs:
        recs = load(rd)
        per = defaultdict(lambda: {"n": 0, "bytes": set(), "values": set(),
                                   "outcomes": defaultdict(int)})
        for r in recs:
            if r["role"] not in ("ladder", "target"):
                continue
            k = "%s|%s|b%d" % (r["arm"], r["carrier_id"], r["byte_index"])
            e = per[k]
            e["n"] += 1
            e["bytes"].add(r["bytes"])
            e["values"].add(r["value"])
            e["outcomes"][r["outcome"]] += 1
        rr = {}
        for k in sorted(per):
            e = per[k]
            rr[k] = {"values_dispatched": len(e["values"]),
                     "distinct_bytes": len(e["bytes"]),
                     "encodable_range": 256,
                     "complete": len(e["bytes"]) == 256,
                     "outcomes": dict(e["outcomes"])}
            if len(e["bytes"]) != len(e["values"]):
                report["under_covered"].append(
                    {"run": rd, "key": k, "values": len(e["values"]),
                     "distinct_bytes": len(e["bytes"]),
                     "why": "distinct encodings < dispatched values -- the "
                            "DEF-0166-1 signature"})
                bad += 1
        report["runs"][rd] = rr
        n_complete = sum(1 for v in rr.values() if v["complete"])
        print("%-40s %4d byte-sweeps, %4d dense-complete (256/256)"
              % (rd, len(rr), n_complete))
    outp = Path(__file__).resolve().parent / "coverage.json"
    outp.write_text(json.dumps(report, indent=1, sort_keys=True))
    print("under-covered byte-sweeps:", bad, "->", outp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
