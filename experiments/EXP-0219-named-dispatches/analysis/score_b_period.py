#!/usr/bin/env python3
"""EXP-0219 AMENDMENT-01: is the bit-6 payload PERIODIC in the dispatch index?

For every (arm, value) with more than one distinct payload, find the smallest
period P that divides the sequence exactly, and check the pre-registered
prediction: P in {4, 8} and every payload count divisible by N/P.
"""
import json
import collections
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def load(r):
    return [json.loads(l) for l in (EXP / "raw" / r / "sweep.jsonl").open()]


def seqs(run):
    per = collections.defaultdict(dict)
    for r in load(run):
        if r["field"] == "mode":
            per[(r["carrier"], r["value"])][r["repeat"]] = json.dumps(
                r["observed"].get("probe"), sort_keys=True)
    return per


def smallest_period(seq):
    n = len(seq)
    for p in range(1, n + 1):
        if n % p:
            continue
        if all(seq[i] == seq[i % p] for i in range(n)):
            return p
    return None


out = {}
for run, N in (("g17p_e0219_B_rep_run01", 16), ("g17p_e0219_B_rep_run02", 16),
               ("g17p_e0219_B_rep_run03", 24)):
    per = seqs(run)
    ent = {"N": N, "unstable": {}, "period_hist": collections.Counter(),
           "counts_ok": 0, "counts_bad": [], "aperiodic": []}
    for (arm, v), d in sorted(per.items()):
        seq = [d[i] for i in sorted(d)]
        if len(set(seq)) < 2:
            continue
        p = smallest_period(seq)
        cnt = sorted(collections.Counter(seq).values(), reverse=True)
        ok = (p in (4, 8)) and all(c % (N // p) == 0 for c in cnt) if p else False
        ent["period_hist"][str(p)] += 1
        ent["unstable"].setdefault(arm, {})[hex(v)] = {"period": p, "counts": cnt}
        if p is None:
            ent["aperiodic"].append([arm, hex(v), cnt])
        elif ok:
            ent["counts_ok"] += 1
        else:
            ent["counts_bad"].append([arm, hex(v), p, cnt])
    ent["period_hist"] = dict(ent["period_hist"])
    ent["n_unstable_total"] = sum(len(x) for x in ent["unstable"].values())
    ent["per_arm_unstable"] = {a: len(x) for a, x in ent["unstable"].items()}
    # bit6-clear control: any unstable value with bit6 == 0?
    ent["unstable_with_bit6_clear"] = [[a, val] for a, x in ent["unstable"].items()
                                       for val in x if not (int(val, 16) & 0x40)]
    out[run] = ent
print(json.dumps(out, indent=1, default=str))
