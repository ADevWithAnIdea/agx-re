#!/usr/bin/env python3
"""EXP-0208 method check -- can the predicate finder REDISCOVER the four walls the
dispatch already documents?  Three of them sit on rows outside this experiment's target
set (they are already emitter-grade), so this is a pure instrument test."""
import json, os, collections, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify_axes import predicate_for, parse_val   # noqa
HERE = os.path.dirname(os.path.abspath(__file__))
TRACKED = set(l.strip() for l in open(os.path.join(HERE, "..", "work", "tracked_files.txt")))
WANT = {("frag_color_pack", "dst"), ("device_store", "index_reg"), ("device_store", "extmode"),
        ("n4_rt_word", "dst"), ("frag_color_pack", "fmt_class")}
per = collections.defaultdict(list)
for line in open(os.path.join(HERE, "..", "work", "raw_index_jsonl.jsonl")):
    g = json.loads(line)
    if g["file"] in TRACKED and (g["instr"], g["field"]) in WANT:
        per[(g["instr"], g["field"], g["exp"], g["carrier"])].append(g)
for k, gs in sorted(per.items()):
    disp, flt, hng = collections.Counter(), collections.Counter(), collections.Counter()
    for g in gs:
        for x in (g.get("values") or []):
            v = parse_val(x);  disp[v] += 1 if v is not None else 0
        for x in (g.get("faultvals") or []):
            v = parse_val(x);  flt[v] += 1 if v is not None else 0
        for x in (g.get("hangvals") or []):
            v = parse_val(x);  hng[v] += 1 if v is not None else 0
    disp.pop(None, None); flt.pop(None, None); hng.pop(None, None)
    allv = sorted(disp)
    fi = {v for v in flt if flt[v] >= disp.get(v, 0) and disp.get(v, 0) > 0}
    hi = {v for v in hng if hng[v] >= disp.get(v, 0) and disp.get(v, 0) > 0}
    if not (fi or hi):
        continue
    print("%-40s exp=%-34s carrier=%-28s runs=%d values=%d" % (".".join(k[:2]), k[2], k[3][:28], len(gs), len(allv)))
    if fi: print("      FAULT %3d -> %s" % (len(fi), predicate_for(sorted(fi), allv)))
    if hi: print("      HANG  %3d -> %s" % (len(hi), predicate_for(sorted(hi), allv)))
