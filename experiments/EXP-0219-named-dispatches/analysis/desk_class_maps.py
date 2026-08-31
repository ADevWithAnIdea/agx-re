#!/usr/bin/env python3
"""EXP-0219 desk step B0b: per-arm payload-CLASS map for tex_sample.mode, from
EXP-0213's three committed quiet orders. Reads committed raw only; writes
nothing into any raw/ tree.

Output: for each arm, a 16x16 table of value -> (class in B1, B2, B3), plus the
distinct payload classes themselves. This is what shows that the instability is
confined to bit6=1 & bit3=0 & bit2=0 and that the alternatives are structured
(a channel reading 0, or a channel whose float has its low 16 bits zero).
"""
import json, sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
RAW = EXP.parent / "EXP-0204-g17p-tex-carrier-dimensions" / "raw"
ORDERS = ["g17p_e0213_B1", "g17p_e0213_B2", "g17p_e0213_B3"]
ARMS = ["tex_sample_msfilt_0", "tex_sample_msfixl_0", "tex_sample_msfixl_1",
        "tex_sample_msgath_0", "tex_sample_mscmp_0", "tex_sample_mscmp_1",
        "tex_sample_msread_0", "tex_sample_msread_1",
        "tex_sample_mslodq_0", "tex_sample_mslodq_1"]


def arm_map(arm):
    per = {}
    for o in ORDERS:
        p = RAW / ("%s_%s" % (o, arm)) / "sweep.jsonl"
        per[o] = {json.loads(l)["value"]: json.loads(l)
                  for l in p.open() if json.loads(l).get("field") == "mode"}
    b = [json.loads(l) for l in (RAW / ("g17p_e0213_B1_%s" % arm) / "sweep.jsonl").open()]
    base = [r for r in b if r.get("field") == "_baseline"][0]["observed"]["probe"]
    cls = {json.dumps(base, sort_keys=True): 0}

    def cid(pl):
        if pl not in cls:
            cls[pl] = len(cls)
        return cls[pl]
    grid = [[cid(json.dumps(per[o][v]["observed"].get("probe"), sort_keys=True))
             for o in ORDERS] for v in range(256)]
    return grid, {v: k for k, v in cls.items()}


for arm in ARMS:
    grid, inv = arm_map(arm)
    print("=== %s   (class 0 == unmutated baseline; %d distinct payloads)"
          % (arm, len(inv)))
    for v in range(256):
        s = "".join(str(x) if x < 10 else chr(ord('a') + x - 10) for x in grid[v])
        print("%02x:%s" % (v, s), end="\n" if v % 16 == 15 else " ")
    for i in sorted(inv):
        d = json.loads(inv[i])
        print("  class %2d %s" % (i, json.dumps(d)[:400]))
    print()
