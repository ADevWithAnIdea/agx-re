#!/usr/bin/env python3
"""Audit EXP-0155's two gated runs: per (instr, field, carrier), how many swept
values moved the observation (match == False).  Reproduces the EXP-0163 target
list of fields never observed to move on any carrier in either run.

Read-only over EXP-0155 raw evidence; writes nothing there.
"""
import json, sys, os, collections

RUNS = sys.argv[1:] or [
    "experiments/EXP-0155-g17p-emit-tex-frag/raw/g17p_20260829_run03/sweep.jsonl",
    "experiments/EXP-0155-g17p-emit-tex-frag/raw/g17p_20260829_run04/sweep.jsonl",
]

# key -> run -> carrier -> {'n':int,'moved':int,'outcomes':Counter}
agg = collections.defaultdict(lambda: collections.defaultdict(
    lambda: collections.defaultdict(lambda: {"n": 0, "moved": 0,
                                             "outcomes": collections.Counter()})))

for path in RUNS:
    run = os.path.basename(os.path.dirname(path))
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            fld = d.get("field")
            if not fld or fld.startswith("_"):
                continue
            key = "%s.%s" % (d["instr"], fld)
            e = agg[key][run][d.get("carrier", "?")]
            e["n"] += 1
            if d.get("match") is False:
                e["moved"] += 1
            e["outcomes"][d.get("outcome", "?")] += 1

out = {}
for key, runs in sorted(agg.items()):
    carriers = set()
    for r in runs.values():
        carriers |= set(r.keys())
    total_moved = sum(c["moved"] for r in runs.values() for c in r.values())
    out[key] = {
        "n_carriers": len(carriers),
        "carriers": sorted(carriers),
        "total_moved": total_moved,
        "per_run": {r: {c: {"n": v["n"], "moved": v["moved"],
                            "outcomes": dict(v["outcomes"])}
                        for c, v in cs.items()}
                    for r, cs in runs.items()},
    }

never = {k: v for k, v in out.items() if v["total_moved"] == 0}
print("total fields swept:", len(out))
print("fields never observed to move on any carrier in either run:", len(never))
for k, v in sorted(never.items(), key=lambda kv: (kv[1]["n_carriers"], kv[0])):
    print("  %-34s carriers=%d  %s" % (k, v["n_carriers"], ",".join(v["carriers"])))

json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "work",
                                 "audit_0155_move_counts.json"), "w"),
          indent=1, sort_keys=True)
