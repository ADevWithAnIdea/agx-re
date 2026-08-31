#!/usr/bin/env python3
"""EXP-0219 part-B: the WITHIN-PROCESS repeat rate for `tex_sample.mode`.

M-B1 (race)               -> within-process disagreement > 0 on the unstable values
M-B2 (per-process state)  -> 100 % within-process agreement
M-B3 (harness artefact)   -> the bit6-CLEAR control set disagrees at a comparable rate

Reads this experiment's own committed raw only.
"""
import json
import collections
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
RUNS = ["g17p_e0219_B_rep_run01", "g17p_e0219_B_rep_run02"]


def load(r):
    return [json.loads(l) for l in (EXP / "raw" / r / "sweep.jsonl").open()]


out = {}
for run in RUNS:
    recs = load(run)
    per = collections.defaultdict(list)
    gate_a = collections.Counter()
    detect = {}
    finals = {}
    for r in recs:
        if r["field"] == "_detect_summary":
            detect[r["carrier"]] = r["outcome"]
        if r["field"] == "_baseline_final":
            finals[r["carrier"]] = r["outcome"]
        if r["field"] != "mode":
            continue
        L = r["observed"].get("_ledger", {})
        gate_a[bool(L.get("gate_a_ok"))] += 1
        key = (r["carrier"], r["value"])
        per[key].append((json.dumps(r["observed"].get("probe"), sort_keys=True),
                         r["outcome"], r["repeat"]))
    arms = sorted({k[0] for k in per})
    ent = {"gate_a": {"ok": gate_a[True], "not_ok": gate_a[False]},
           "gate_b_detect": detect, "baseline_final": finals, "arms": {}}
    for arm in arms:
        b6, b6n, cl, cln = 0, 0, 0, 0
        unstable_vals = {}
        for (a, v), obs in per.items():
            if a != arm:
                continue
            distinct = len({o[0] for o in obs})
            bit6 = bool(v & 0x40)
            if bit6:
                b6n += 1
                b6 += (distinct > 1)
            else:
                cln += 1
                cl += (distinct > 1)
            if distinct > 1:
                cnt = collections.Counter(o[0] for o in obs)
                unstable_vals[v] = {"n_repeats": len(obs), "n_distinct": distinct,
                                    "counts": sorted(cnt.values(), reverse=True)}
        ent["arms"][arm] = {
            "bit6_set_values": b6n, "bit6_set_unstable_within_process": b6,
            "bit6_clear_values": cln, "bit6_clear_unstable_within_process": cl,
            "unstable_detail": {str(k): v for k, v in sorted(unstable_vals.items())}}
    out[run] = ent

# cross-run: same (arm,value) across the two runs (different processes)
a, b = [load(r) for r in RUNS]


def pay(recs):
    d = collections.defaultdict(set)
    for r in recs:
        if r["field"] == "mode":
            d[(r["carrier"], r["value"])].add(
                json.dumps(r["observed"].get("probe"), sort_keys=True))
    return d


pa, pb = pay(a), pay(b)
shared = sorted(set(pa) & set(pb))
cross = collections.defaultdict(lambda: {"same": 0, "diff": 0, "n": 0})
for k in shared:
    arm, v = k
    e = cross[(arm, bool(v & 0x40))]
    e["n"] += 1
    if pa[k] == pb[k]:
        e["same"] += 1
    else:
        e["diff"] += 1
out["cross_run_payload_set_equality"] = {
    "%s bit6=%d" % (arm, int(b6)): v for (arm, b6), v in sorted(cross.items())}
print(json.dumps(out, indent=1))
