#!/usr/bin/env python3
"""EXP-0213 -- per-(carrier,value) payload STABILITY across N runs of one field.

    python3 analysis/stability.py <field> <run1.jsonl> ... <runN.jsonl>

Reports, for every (carrier, value): how many DISTINCT observed payloads the N runs produced.
1 = stable.  2 = bistable.  N = a fresh answer every run.  This distinguishes "the pair I
happened to take disagreed" from "this encoding does not produce a reproducible observation".
"""
import json
import sys
from collections import Counter, defaultdict

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
    paths = sys.argv[2:]
    maps = [idx(load(p), field) for p in paths]
    common = set(maps[0])
    for m in maps[1:]:
        common &= set(m)
    per = defaultdict(Counter)
    unstable = defaultdict(list)
    for k in sorted(common, key=str):
        pays = [json.dumps(strip_volatile(m[k]["observed"]), sort_keys=True, default=str)
                for m in maps]
        n = len(set(pays))
        per[k[0]][n] += 1
        if n > 1:
            unstable[k[0]].append((k[1], n, [m[k].get("outcome") for m in maps]))
    print("field=%s  runs=%d  shared (carrier,value) keys=%d"
          % (field, len(paths), len(common)))
    for p in paths:
        print("   run: %s" % p.split("/")[-1])
    for car in sorted(per):
        d = dict(per[car])
        print("  %-24s distinct-payload-count histogram %s" % (car, d))
        if unstable[car]:
            vs = [u[0] for u in unstable[car]]
            print("      unstable values (%d): %s" % (len(vs), vs[:48]))
    tot = sum(sum(c.values()) for c in per.values())
    bad = sum(v for c in per.values() for k, v in c.items() if k > 1)
    print("  TOTAL keys %d ; unstable %d ; stable %d (%.4f%%)"
          % (tot, bad, tot - bad, 100.0 * (tot - bad) / tot if tot else 0))


if __name__ == "__main__":
    main()
