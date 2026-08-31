#!/usr/bin/env python3
"""EXP-0213 -- localise a cross-run disagreement: WHICH values, and WHICH observable moved.

    python3 analysis/disagree_detail.py <field> <runA.jsonl> <runB.jsonl> [more runs...]

For every (carrier, value) of one field, prints the set of runs that disagree with run A and
which top-level key of `observed` differs.  A disagreement confined to one probe slot is a
property of the observation path; one that moves the whole payload is not.
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pairwise import load, strip_volatile                            # noqa: E402


def idx(R, field):
    d = {}
    for r in R:
        if r.get("field") == field and isinstance(r.get("value"), int) and r["value"] >= 0:
            d[(r["carrier"], r["value"])] = r
    return d


def main():
    field = sys.argv[1]
    runs = sys.argv[2:]
    maps = [idx(load(p), field) for p in runs]
    names = [p.split("/")[-1].replace(".jsonl", "") for p in runs]
    keys = sorted(set(maps[0]), key=str)
    percar = defaultdict(lambda: defaultdict(int))
    whichkey = defaultdict(int)
    detail = defaultdict(list)
    for k in keys:
        rs = [m.get(k) for m in maps]
        if any(r is None for r in rs):
            continue
        pays = [json.dumps(strip_volatile(r["observed"]), sort_keys=True, default=str)
                for r in rs]
        if len(set(pays)) == 1:
            continue
        car, val = k
        percar[car]["disagreeing_values"] += 1
        outs = [r.get("outcome") for r in rs]
        percar[car]["|".join(sorted(set(outs)))] += 1
        obs = [strip_volatile(r["observed"]) for r in rs]
        allk = set()
        for o in obs:
            allk |= set(o)
        for kk in sorted(allk):
            vs = {json.dumps(o.get(kk), sort_keys=True, default=str) for o in obs}
            if len(vs) > 1:
                whichkey[kk] += 1
        detail[car].append((val, outs))
    print("runs:", names)
    print("field:", field)
    for car in sorted(percar):
        print("  %-24s %s" % (car, dict(percar[car])))
        vals = sorted(v for v, _ in detail[car])
        print("      values: %s%s" % (vals[:40], " ..." if len(vals) > 40 else ""))
    print("  observed keys that differ (count of disagreeing cases):", dict(whichkey))


if __name__ == "__main__":
    main()
