#!/usr/bin/env python3
"""EXP-0219 A2: the fetch index width, scored against a prediction made from
OUR OWN MSL SOURCE rather than from the observations being scored.

`kernels/carrier_const.metal` declares 48 constants; constant i has
    low  half = 0x1000 + i        high half = 0x3F80 + i
by construction (`as_type<float>((0x3F80+i)<<16 | (0x1000+i))`), and the two
ranges are disjoint, so every 16-bit value observed in the file identifies
exactly which constant it came from and which half of it.

The FIT uses half-indices 0..31 ONLY (the declared fit rule).  Those show the
layout `half 14+2i -> low(i)`, `half 15+2i -> high(i)` for i = 0..8.  The
LAYOUT is then extrapolated and every half-index >= 32 is a HELD-OUT
PREDICTION: nothing at index >= 32 was used to build it.
"""
import json
from pathlib import Path
import collections

EXP = Path(__file__).resolve().parent.parent
RUNS = ["g17p_e0219_A_const_run01", "g17p_e0219_A_const_run02",
        "g17p_e0219_A_dag_run01", "g17p_e0219_A_dag_run02"]


def predicted_const_file(j):
    """Half-index -> value, extrapolated from the fit region 14..31 only."""
    if j < 14:
        return None                        # not predicted; driver-owned prefix
    d = j - 14
    i = d // 2
    if i > 47:
        return 0                           # only 48 constants exist
    return (0x1000 + i) if d % 2 == 0 else (0x3F80 + i)


out = {}
for run in RUNS:
    recs = [json.loads(l) for l in (EXP / "raw" / run / "sweep.jsonl").open()]
    seen = {}
    for r in recs:
        b = bytes.fromhex(r["ledger"]["actual_bytes"])
        if r["arm"] != "b8imm" or b[9] != 0x2e or not r["ledger"]["gate_a_ok"]:
            continue
        if r["outcome"] in ("hang", "fault", "measurement_failure", "undecodable"):
            continue
        idx8 = ((b[7] >> 3) & 0x1F) | ((b[8] & 7) << 5)
        seen.setdefault(idx8, set()).add(r["recovered_A"])
    single = {k: list(v)[0] for k, v in seen.items() if len(v) == 1}
    multi = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
    nz = {k: v for k, v in single.items() if v}
    ent = {"indices_dispatched": len(seen), "single_valued": len(single),
           "multi_valued": multi,
           "n_nonzero": len(nz),
           "max_nonzero_index": max(nz) if nz else None,
           "nonzero_above_31": sorted(k for k in nz if k >= 32)[:10],
           "n_nonzero_above_31": sum(1 for k in nz if k >= 32)}
    if "const" in run:
        hit = tot = 0
        bad = []
        for j, v in sorted(single.items()):
            p = predicted_const_file(j)
            if p is None or j < 32:
                continue                    # fit region / driver prefix
            tot += 1
            if v == p:
                hit += 1
            elif len(bad) < 12:
                bad.append({"half_index": j, "observed": hex(v),
                            "predicted_from_MSL": hex(p)})
        ent["heldout_index>=32_vs_MSL_prediction"] = "%d/%d" % (hit, tot)
        ent["heldout_mismatches"] = bad
        ent["file_tail"] = {str(j): hex(single[j])
                            for j in sorted(single) if 104 <= j <= 130}
    out[run] = ent
print(json.dumps(out, indent=1))
