#!/usr/bin/env python3
"""EXP-0160 DESK CHECK (no hardware): does the frozen model class explain the
eight target fields on EXP-0154's already-committed dense G17P sweeps?

Run BEFORE building the probe so the sweep is designed against a model class
that can actually close the fields. Nothing here is promoted; EXP-0160's own
gated runs supply the evidence.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import modelfit as MF

REPO = Path(__file__).resolve().parents[3]
E154 = REPO / "experiments" / "EXP-0154-g17p-emit-alu"
TARGETS = [("falu2_ext","ctrl",7),("falu3","op",8),("falu3_ext","op",8),
           ("iminmax","srcB",8),("isel8","cmp_mode",8),("imad","srcC_desc",8),
           ("half_pack","src",8)]

def load(run, want):
    out = {}
    for ln in (E154/"raw"/run/"sweep.jsonl").open():
        try: r = json.loads(ln)
        except Exception: continue
        if (r["instr"], r["field"]) in want:
            out[(r["instr"], r["field"], r["value"])] = r
    return out

want = set((i,f) for i,f,_ in TARGETS)
A = load("g17p_20260829_run02", want)
B = load("g17p_20260829_run04", want)

for instr, field, w in TARGETS:
    print("="*76)
    print("%s.%s  (w=%d)" % (instr, field, w))
    sigmap, dumps, outc, base = {}, {}, {}, None
    agree = disagree = 0
    for v in range(1 << w):
        ra, rb = A.get((instr,field,v)), B.get((instr,field,v))
        if ra is None or rb is None:
            continue
        if base is None and ra["oracle"]["digest"]:
            d = ra["oracle"]["digest"]; base = [int(d[i*8:(i+1)*8],16) for i in range(16)]
        sa = MF.sig(ra["observed"]["regs"], base) if base else None
        sb = MF.sig(rb["observed"]["regs"], base) if base else None
        if ra["outcome"] != rb["outcome"] or sa != sb:
            disagree += 1; continue
        agree += 1
        outc[v] = ra["outcome"]
        sigmap[v] = sa if sa is not None else "FAULT:" + ra["outcome"]
        dumps[v] = ra["observed"]["regs"]
    print("  gated agree=%d disagree=%d  outcomes=%s" % (agree, disagree, dict(Counter(outc.values()))))
    okv = [v for v in sigmap if outc[v] == "ok"]
    m, val, exc = MF.mask_rule(okv, list(sigmap), w)
    print("  M1 mask: (v & 0x%02x)==0x%02x  exceptions=%s  dense=%s"
          % (m or 0, val or 0, exc, len(sigmap) == (1 << w)))
    rel = MF.relevant_bits(sigmap, w)
    tab, texc, sup, relb = MF.class_table(sigmap, rel, w)
    print("  M2 relevant bits=%s (|R|=%d, inert=%s) classes=%d min_support=%d exceptions=%d"
          % (relb, len(relb), [b for b in range(w) if b not in relb], len(tab), sup, texc))
    if len(relb) <= w - 2 and texc == 0:
        print("     -> M2 EXACT: complete class table, every class confirmed by >=%d values" % sup)
        for k in sorted(tab):
            bits = "".join(str((k >> j) & 1) for j in range(len(relb)))[::-1]
            print("        bits%s=%s -> %s" % (relb[::-1], bits, tab[k]))
    sc = MF.regmap_score(dumps, base or [0]*16)
    for role in ("released","written"):
        b = MF.best_regmodel(sc[role])
        if b: print("  M3 %s: %s %s" % (role, b[0], b[1]))
