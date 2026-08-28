#!/usr/bin/env python3
"""EXP-0148 -- per-file comparison of two variants' strict/resync summaries.
Usage: python3 analysis/ab_diff.py <A> <B>   (variant dir names under raw/ab/)"""
import json, sys
A, B = sys.argv[1], sys.argv[2]
for kind in ("strict", "resync"):
    a = json.load(open("raw/ab/%s/%s.json" % (A, kind)))
    b = json.load(open("raw/ab/%s/%s.json" % (B, kind)))
    ga, gb = set(a["gap_files"]), set(b["gap_files"])
    print("== %s  %s->%s : clean %d -> %d ; gap_bytes %d -> %d" % (
        kind, A, B, a["clean_files"], b["clean_files"], a["gap_bytes"], b["gap_bytes"]))
    print("   FIXED  (%d): %s" % (len(ga - gb), sorted(ga - gb)[:60]))
    print("   BROKEN (%d): %s" % (len(gb - ga), sorted(gb - ga)[:60]))
