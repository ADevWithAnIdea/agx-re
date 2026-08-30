#!/usr/bin/env python3
"""EXP-0184 exact value->behaviour partition for the fields that MOVED.

    python3 analysis/partitions.py raw/<run01> raw/<run02>

A `hardware-run` label licenses an implementer to CHOOSE a value, so the verdict
is only half the deliverable: the other half is the exact set of values that
produce which behaviour, reproduced identically in both gated runs. Anything
that differs between runs is printed rather than averaged away.

Output: `analysis/partitions.json` + a human table on stdout.
"""
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def load(d):
    return [json.loads(l) for l in (Path(d) / "sweep.jsonl").read_text().splitlines() if l.strip()]


def main():
    r1, r2 = load(sys.argv[1]), load(sys.argv[2])
    idx = {}
    for tag, rs in (("r1", r1), ("r2", r2)):
        for r in rs:
            if r.get("role") in ("target", "control"):
                idx[(tag, r["arm"], r["value"])] = r
    arms = sorted({k[1] for k in idx})
    out = {}
    for arm in arms:
        vals = sorted({k[2] for k in idx if k[1] == arm})
        groups = collections.defaultdict(list)
        mismatch = []
        for v in vals:
            a, b = idx.get(("r1", arm, v)), idx.get(("r2", arm, v))
            if not a or not b:
                continue
            ka = (a["outcome"], json.dumps(a["observed"].get("vals")))
            kb = (b["outcome"], json.dumps(b["observed"].get("vals")))
            if ka != kb:
                mismatch.append({"value": v, "r1": ka, "r2": kb})
                continue
            groups[ka].append(v)
        out[arm] = {
            "n_values": len(vals),
            "cross_run_mismatches": mismatch,
            "partition": [{"outcome": k[0], "observed": json.loads(k[1]),
                           "n": len(vs), "values": vs}
                          for k, vs in sorted(groups.items(), key=lambda x: -len(x[1]))],
        }
    (EXP / "analysis" / "partitions.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    for arm in arms:
        d = out[arm]
        if len(d["partition"]) <= 1 and not d["cross_run_mismatches"]:
            continue
        print("=== %s  (%d values, %d cross-run mismatches)"
              % (arm, d["n_values"], len(d["cross_run_mismatches"])))
        for g in d["partition"]:
            vs = g["values"]
            rng = _ranges(vs)
            obs = g["observed"]
            if isinstance(obs, list) and len(obs) > 8:
                obs = obs[:8] + ["..."]
            print("   %-12s n=%-4d %-52s %s" % (g["outcome"], g["n"], rng, obs))
    print("\nwrote", EXP / "analysis" / "partitions.json")


def _ranges(vs):
    out, s, p = [], vs[0], vs[0]
    for v in vs[1:]:
        if v == p + 1:
            p = v
            continue
        out.append("%d" % s if s == p else "%d..%d" % (s, p))
        s = p = v
    out.append("%d" % s if s == p else "%d..%d" % (s, p))
    t = ",".join(out)
    return t if len(t) <= 50 else t[:47] + "..."


if __name__ == "__main__":
    main()
