#!/usr/bin/env python3
import json, collections, sys
for tag, f in [("OWN", "own_before.json"), ("TP", "tp_before.json")]:
    try:
        j = json.load(open(f))
    except FileNotFoundError:
        continue
    tot = j["total_bytes"]; des = j["desync_bytes"]
    print("=== %s: total=%d desync=%d (%.2f%%)  named=%.2f%% raw=%.2f%% cov=%.2f%% ===" % (
        tag, tot, des, 100*des/tot, j["pct_named"], j["pct_raw"], j["pct_named"]+j["pct_raw"]))
    lb = collections.Counter()
    for k, v in j["byte0_desync"].items():
        b0 = int(k, 16); lb[b0 & 0x0f] += v["bytes"]
    parts = ["_%x:%d" % (n, lb[n]) for n in sorted(lb, key=lambda x: -lb[x])]
    print("  desync bytes by LOW nibble:", " ".join(parts))
    top = sorted(j["byte0_desync"].items(), key=lambda kv: -kv[1]["bytes"])[:24]
    print("  top byte0 desync (byte0: regions r / bytes b : ctx):")
    for k, v in top:
        print("     %s: %5dr %6db  %s" % (k, v["regions"], v["bytes"], v["sample"]))
    print()
