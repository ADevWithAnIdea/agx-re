#!/usr/bin/env python3
"""EXP-0176: pick 10 PROVENANCE.md rows at random (fixed seed) for manual reproduction.

Seed is frozen at 20260830 so the selection is reproducible and was NOT chosen
after seeing which rows are convenient.
    python3 experiments/EXP-0176-provenance-chain/analysis/sample_rows.py
"""
import random, os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ROOT=os.path.abspath(os.path.join(HERE,'..','..','..'))
lines=open(os.path.join(ROOT,'PROVENANCE.md')).read().splitlines()
rows=[]
for ln,line in enumerate(lines,1):
    if not line.startswith('|'): continue
    c=[x.strip() for x in line.strip().strip('|').split('|')]
    if len(c)<5: continue
    if c[0].lower().startswith('date') or set(c[0])<=set('-: '): continue
    rows.append(ln)
random.seed(20260830)
sel=sorted(random.sample(rows,10))
print("rows in table:",len(rows))
print("selected lines:",sel)
for ln in sel:
    print("\n"+"="*90)
    print("LINE",ln)
    print(lines[ln-1][:1800])
