#!/usr/bin/env python3
"""EXP-0194 step 7: re-derive the ONE surviving claim straight from committed raw.

Reads only experiments/EXP-0138-m4-emit-falu/raw/*/sweep.jsonl and
experiments/EXP-0154-g17p-emit-alu/raw/*/sweep.jsonl, and prints every case that
mentions falu2_ext.srcB_neg, so a reviewer can check the claim without trusting any
intermediate this experiment produced.
"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
START, WIDTH = 43, 1          # db.json falu2_ext.srcB_neg

def bit(b):
    return (int.from_bytes(bytes.fromhex(b), "little") >> START) & ((1 << WIDTH) - 1)

rows = []
for p in sorted(glob.glob(os.path.join(ROOT, "experiments", "EXP-01[35][48]*", "raw", "*", "sweep.jsonl"))):
    for ln, line in enumerate(open(p, errors="replace"), 1):
        if '"srcB_neg"' not in line:
            continue
        r = json.loads(line)
        if r.get("instr") != "falu2_ext" or r.get("field") != "srcB_neg":
            continue
        rows.append((os.path.relpath(p, ROOT), ln, r))

print("%-62s %-5s %-18s %-4s %-4s %-6s %-6s %s"
      % ("raw file", "line", "bytes", "val", "bit", "outc", "match", "observed -> oracle"))
for p, ln, r in rows:
    o = json.dumps(r.get("observed"))
    a = json.dumps(r.get("oracle"))
    print("%-62s %-5d %-18s %-4s %-4s %-6s %-6s %s -> %s"
          % (p.replace("experiments/", ""), ln, r["bytes"], r.get("value"), bit(r["bytes"]),
             r.get("outcome"), r.get("match"), o[:60], a[:60]))

print()
outside = {(len(r["bytes"]), int.from_bytes(bytes.fromhex(r["bytes"]), "little")
            & ~(((1 << WIDTH) - 1) << START)) for _, _, r in rows}
print("distinct 'everything except bit 43' values, per experiment:")
for e in ("EXP-0138", "EXP-0154"):
    s = {(len(r["bytes"]), int.from_bytes(bytes.fromhex(r["bytes"]), "little")
          & ~(((1 << WIDTH) - 1) << START)) for p, _, r in rows if e in p}
    print("   %s: %d  (1 == the change is isolated to bit 43)" % (e, len(s)))
