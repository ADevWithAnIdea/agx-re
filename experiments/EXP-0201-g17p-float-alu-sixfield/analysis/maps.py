#!/usr/bin/env python3
"""EXP-0201 semantic maps: what each field VALUE made the hardware compute.

    python3 analysis/maps.py raw/<run01> raw/<run02> [...]   -> analysis/maps.json

`verdicts.py` decides promotion. This script does the other half: it reports, per
arm, the value -> NAMED HOST FUNCTION map, the accept set, and the smallest bit
rule that explains the accept set. "Moved" says the bits are not ignored; the
named function says what they selected, and that is what an emitter needs.

It also reports the AGREEMENT BETWEEN RUNS on the named function, which is a
stricter and more meaningful cross-run check than payload equality alone: two
runs can differ in a poison word and still agree on the arithmetic.
"""
import collections
import glob
import itertools
import json
import os
import sys

HARD = {"fault", "hang", "undecodable", "measurement_failure", "invalid_run",
        "nondeterministic"}


def load(dirs):
    out = []
    for d in dirs:
        run = os.path.basename(os.path.normpath(d))
        for f in sorted(glob.glob(os.path.join(d, "sweep.jsonl"))):
            for ln in open(f, errors="replace"):
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                r["_run"] = run
                out.append(r)
    return out


def bit_rule(accept, width_bits=8):
    """Smallest (mask, value) with {v : v & mask == value} == accept, if one
    exists. Reported because an emitter needs a rule, not a list."""
    best = None
    for mask in range(1 << width_bits):
        vals = {v & mask for v in accept}
        if len(vals) != 1:
            continue
        val = vals.pop()
        if {v for v in range(1 << width_bits) if v & mask == val} == set(accept):
            if best is None or bin(mask).count("1") < bin(best[0]).count("1"):
                best = (mask, val)
    return None if best is None else {"mask": best[0], "value": best[1],
                                      "expr": "(v & 0x%02X) == 0x%02X" % best}


def main():
    dirs = sys.argv[1:]
    if not dirs:
        print(__doc__)
        return 2
    exp = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    recs = load(dirs)
    runs = sorted({r["_run"] for r in recs})
    arms = sorted({r["arm"] for r in recs
                   if r.get("role") == "target" and r.get("arm")})
    out = {}
    for arm in arms:
        rs = [r for r in recs if r.get("arm") == arm]
        instr = rs[0]["instr"]
        field = rs[0]["field"]
        width = rs[0]["width"]
        per_run = {}
        for run in runs:
            rr = {r["value"]: r for r in rs if r["_run"] == run}
            if not rr:
                continue
            per_run[run] = {
                "accept": sorted(v for v, r in rr.items() if r["outcome"] == "ok"),
                "fn": {v: (r["observed_fn"] if r["outcome"] not in HARD
                           else "HARD:" + r["outcome"]) for v, r in rr.items()},
                "outcomes": dict(collections.Counter(r["outcome"] for r in rr.values())),
            }
        if not per_run:
            continue
        r0 = per_run[runs[0]] if runs[0] in per_run else list(per_run.values())[0]
        acc = r0["accept"]
        # cross-run agreement on the NAMED FUNCTION (stricter than "it moved")
        fn_agree = None
        ks = [k for k in runs if k in per_run]
        if len(ks) >= 2:
            a, b = per_run[ks[0]]["fn"], per_run[ks[1]]["fn"]
            common = set(a) & set(b)
            dis = sorted(v for v in common if a[v] != b[v])
            fn_agree = {"common": len(common), "disagree": len(dis),
                        "pct": 100.0 * (1 - len(dis) / max(len(common), 1)),
                        "disagreeing_values": dis[:32]}
        by_fn = collections.defaultdict(list)
        for v, f in r0["fn"].items():
            by_fn[str(f)].append(v)
        out[arm] = {
            "instr": instr, "field": field, "width": width,
            "carrier": rs[0]["carrier"], "occ": rs[0].get("occ"),
            "baseline_value": rs[0].get("baseline_value"),
            "accept_set": acc, "accept_hex": [hex(v) for v in acc],
            "accept_bit_rule": bit_rule(acc, min(width, 8)) if acc else None,
            "outcomes_run0": r0["outcomes"],
            "value_classes": {k: {"n": len(v), "values": sorted(v)[:64]}
                              for k, v in sorted(by_fn.items(), key=lambda x: -len(x[1]))},
            "named_function_cross_run": fn_agree,
        }
    json.dump(out, open(os.path.join(exp, "analysis", "maps.json"), "w"),
              indent=1, default=str)
    for arm, e in sorted(out.items()):
        fa = e["named_function_cross_run"]
        print("%-38s accept=%-2d %-28s fn-agree=%s"
              % (arm, len(e["accept_set"]),
                 (e["accept_bit_rule"] or {}).get("expr", "(no single bit rule)"),
                 ("%.2f%% (%d/%d)" % (fa["pct"], fa["disagree"], fa["common"]))
                 if fa else "n/a"))
        for k, v in list(e["value_classes"].items())[:6]:
            print("      %-14s n=%-4d %s" % (k, v["n"],
                                             [hex(x) for x in v["values"][:8]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
