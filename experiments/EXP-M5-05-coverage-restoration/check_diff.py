#!/usr/bin/env python3
# Diff two validate.py JSON outputs. Flags coverage/desync deltas and, crucially,
# any REAL-op (non operand_word / pad_operand) named-count DROP -- the anti-chopping
# invariant. A clean win = cov up, desync down, zero real-op drops.
import sys, json
a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2]))
label=sys.argv[3] if len(sys.argv)>3 else ""
FILLER={'operand_word','pad_operand'}
print("==== %s ====" % label)
print("cov%%   : %.3f -> %.3f  (%+.3f)" % (a['cov_pct'], b['cov_pct'], b['cov_pct']-a['cov_pct']))
print("desync%%: %.3f -> %.3f  (%+.3f)" % (a['desync_pct'], b['desync_pct'], b['desync_pct']-a['desync_pct']))
print("desync bytes: %d -> %d (%+d)" % (a['desync_bytes'], b['desync_bytes'], b['desync_bytes']-a['desync_bytes']))
am=a['mnem']; bm=b['mnem']
drops=[]; gains=[]
for k in set(am)|set(bm):
    d=bm.get(k,0)-am.get(k,0)
    if d==0: continue
    if k in FILLER: gains.append((d,k)) if d>0 else drops.append((d,k))
    else:
        (drops if d<0 else gains).append((d,k))
realdrops=[(d,k) for d,k in drops if k not in FILLER]
print("REAL-OP DROPS (must be empty!):", sorted(realdrops))
print("filler delta:", {k:bm.get(k,0)-am.get(k,0) for k in FILLER})
print("top real-op gains:", sorted([(d,k) for d,k in gains if k not in FILLER], reverse=True)[:12])
# byte0 desync deltas
ad=a['byte0_desync']; bd=b['byte0_desync']
rows=[]
for g in set(ad)|set(bd):
    ab=ad.get(g,{}).get('bytes',0); bb=bd.get(g,{}).get('bytes',0)
    if ab-bb!=0: rows.append((bb-ab, g, ab, bb))
print("byte0 desync-byte reductions (neg=better):")
for d,g,ab,bb in sorted(rows)[:16]:
    print("   %s: %d -> %d (%+d)" % (g, ab, bb, d))
