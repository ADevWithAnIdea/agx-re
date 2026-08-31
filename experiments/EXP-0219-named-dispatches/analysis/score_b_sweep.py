#!/usr/bin/env python3
"""EXP-0219 part-B: the full 256-value `tex_sample.mode` map on nine arms,
including the three arms EXP-0204 never armed (the LAST texture instruction of
`msread` and of `mslodq`, and the one-instruction carrier `msread1`).

Per arm: which bits move the observable at all, whether bit 6 changes anything,
and the run01 x run02 (forward x reverse) agreement.
"""
import json
import collections
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
RUNS = ["g17p_e0219_B_sweep_run01", "g17p_e0219_B_sweep_run02"]


def load(r):
    return [json.loads(l) for l in (EXP / "raw" / r / "sweep.jsonl").open()]


def maps(recs):
    base, per = {}, collections.defaultdict(dict)
    for r in recs:
        if r["field"] == "_" and "baseline (unmutated)" in r.get("note", ""):
            base.setdefault(r["carrier"],
                            json.dumps(r["observed"].get("probe"), sort_keys=True))
        if r["field"] == "mode":
            per[r["carrier"]][r["value"]] = json.dumps(
                r["observed"].get("probe"), sort_keys=True)
    return base, per


A, B = [maps(load(r)) for r in RUNS]
out = {}
arms = sorted(A[1])
for arm in arms:
    pa, pb = A[1][arm], B[1][arm]
    agree = sum(1 for v in range(256) if pa.get(v) == pb.get(v))
    dis = [v for v in range(256) if pa.get(v) != pb.get(v)]
    # bit liveness: for each bit, count values whose payload changes when the
    # bit is flipped (run01)
    live = {}
    for bit in range(8):
        m = 1 << bit
        n = sum(1 for v in range(256) if (v & m) == 0 and pa.get(v) != pa.get(v | m))
        live["bit%d" % bit] = "%d/128" % n
    # bit6 restricted to the quadrant the desk step named
    q = [v for v in range(256) if not (v & 0x40) and not (v & 0x08) and not (v & 0x04)]
    live["bit6 within bit3=0,bit2=0"] = "%d/%d" % (
        sum(1 for v in q if pa.get(v) != pa.get(v | 0x40)), len(q))
    out[arm] = {"distinct_payloads_run01": len(set(pa.values())),
                "values_equal_to_baseline_run01":
                    sum(1 for v in range(256) if pa.get(v) == A[0][arm]),
                "run01_x_run02_agreement": "%d/256" % agree,
                "disagreeing_values": [hex(v) for v in dis],
                "bit_liveness_run01": live}
print(json.dumps(out, indent=1))
