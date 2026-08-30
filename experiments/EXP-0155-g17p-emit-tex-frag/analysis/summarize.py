#!/usr/bin/env python3
"""summarize.py -- EXP-0155: derive the exact value->outcome maps and bit rules
from the two gated runs, as machine-checked SET IDENTITIES rather than by
eyeballing ranges.

    python3 analysis/summarize.py --run01 <id> --run02 <id>

Writes analysis/bit_rules.json and prints the rules it could prove.
CLEAN-ROOM: pure analysis of our own append-only raw records.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)


def load(rid):
    by = collections.defaultdict(dict)
    with open(os.path.join(EXP, "raw", rid, "sweep.jsonl")) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            if r["field"].startswith("_"):
                continue
            by[(r["instr"], r["carrier"], r["field"])][r["value"]] = r["outcome"]
    return by


def modrule(vals, universe):
    """If `vals` is exactly {v in universe : v % m in R} for some m in 2,4,8,16,32,
    return (m, sorted(R)).  Exact set identity, not an approximation."""
    S = set(vals)
    for m in (2, 4, 8, 16, 32, 64, 128):
        R = {v % m for v in S}
        pred = {v for v in universe if v % m in R}
        if pred == S:
            return m, sorted(R)
    return None


def maskrule(vals, universe):
    """If `vals` is exactly {v : v & mask == want} for some mask, return it."""
    S = set(vals)
    if not S:
        return None
    for mask in range(1, 256):
        wants = {v & mask for v in S}
        if len(wants) > 8:
            continue
        pred = {v for v in universe if (v & mask) in wants}
        if pred == S:
            return mask, sorted(wants)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01", required=True)
    ap.add_argument("--run02", required=True)
    args = ap.parse_args()
    a, b = load(args.run01), load(args.run02)

    rules = {}
    for key in sorted(set(a) & set(b)):
        ma, mb = a[key], b[key]
        common = sorted(set(ma) & set(mb))
        agree = [v for v in common if ma[v] == mb[v]]
        if len(agree) < 8:
            continue
        universe = set(agree)
        buckets = collections.defaultdict(list)
        for v in agree:
            buckets[ma[v]].append(v)
        entry = {"n_common": len(common), "n_agree": len(agree),
                 "counts": {k: len(v) for k, v in buckets.items()}, "rules": {}}
        for outcome, vals in buckets.items():
            if not (0 < len(vals) < len(agree)):
                continue
            mr = modrule(vals, universe)
            if mr:
                entry["rules"][outcome] = {"kind": "modulo", "m": mr[0],
                                           "residues": mr[1],
                                           "statement": f"outcome `{outcome}` iff "
                                                        f"(value mod {mr[0]}) in {mr[1]}"}
                continue
            kr = maskrule(vals, universe)
            if kr:
                entry["rules"][outcome] = {"kind": "mask", "mask": kr[0],
                                           "values": kr[1],
                                           "statement": f"outcome `{outcome}` iff "
                                                        f"(value & {kr[0]:#04x}) in "
                                                        f"{[hex(x) for x in kr[1]]}"}
        if len(vals := buckets.get("ok", [])) == len(agree):
            entry["rules"]["inert"] = {"kind": "inert",
                                       "statement": f"ALL {len(agree)} agreed values "
                                                    f"leave the observation identical "
                                                    f"to the unmutated baseline"}
        rules["|".join(key)] = entry

    with open(os.path.join(HERE, "bit_rules.json"), "w") as f:
        json.dump(rules, f, indent=1, sort_keys=True)
    n = sum(1 for v in rules.values() if v["rules"])
    print(f"{len(rules)} (instr,arm,field) triples cross-run comparable; "
          f"{n} have an exact rule")
    for k, v in sorted(rules.items()):
        for o, r in v["rules"].items():
            print(f"  {k:60s} {r['statement']}")


if __name__ == "__main__":
    main()
