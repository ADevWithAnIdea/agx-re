#!/usr/bin/env python3
"""solvemip.py — EXP-M4-07 TIL-4 mip-chain packing model-checker (per bpp).

For a typrobe2 --upload --mips capture (level L texel (x,y) = hh(x,y,L,k)), locate
the backing BO+base, then model-check the mip packing:
  level L intra-twiddle: tiledMorton(x,y, T(bpp), cols_L)  (cols_L via G granule)
  padLevelBytes(L)     : max( padW_L * padH_L * bpp , 0x80 )   (0x80 min slot)
  offset(L)            : sum_{i<L} padLevelBytes(i)
Predict each texel's byte and count mismatches over ALL levels. 0 mismatch => model
confirmed. Reports per-level offset + total vs BO size. Clean-room: DATA bytes only.
Usage: solvemip.py DUMPDIR --fmt r16uint --w 320 --h 320 --mips 9 [--label NAME]
"""
import argparse, glob, os, re, sys, math
from solve3d import load, hh, expect_bytes, morton, TYPECODE
BPP={'r8uint':1,'r16uint':2,'r32uint':4,'rg32uint':8,'rgba32uint':16}

def nextpow2(n): return 1<<((n-1).bit_length()) if n>1 else 1
def pad_axis_w(W,T,G):
    if W<T: return nextpow2(W)
    nt=-(-W//T); cols=nt if nt<=1 else ((nt+G-1)//G)*G
    return cols*T
def pad_axis_h(H,T):
    if H<T: return nextpow2(H)
    return (-(-H//T))*T

def find_backing(bos,W,H):
    cands=[]
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w0=int.from_bytes(d[o:o+4],'little'); w1=int.from_bytes(d[o+4:o+8],'little')
            w2=int.from_bytes(d[o+8:o+12],'little'); w3=int.from_bytes(d[o+12:o+16],'little')
            if (w0&0xf)!=2: continue
            width=(((w0>>28)&0xf)|((w1&0x3ff)<<4))+1; height=((w1>>10)&0x3fff)+1
            if width!=W or height!=H: continue
            bva=(w2|((w3&0xfff)<<32))<<4
            tgt=[bb for bb in bos if bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size']]
            if tgt: cands.append((bva,[w0,w1,w2,w3],max(tgt,key=lambda bb:bb['size'])))
    if not cands: return None,None,None
    return max(cands,key=lambda c:c[2]['size'])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--fmt',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--mips',type=int,required=True); ap.add_argument('--label',default=None)
    a=ap.parse_args(); fmt=a.fmt; W=a.w; H=a.h; M=a.mips; bpp=BPP[fmt]
    label=a.label or os.path.basename(a.dumpdir.rstrip('/'))
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    bva,w,bo=find_backing(bos,W,H)
    if bva is None: print(f"{label}: desc {W}x{H} NOT FOUND"); return 1
    base=bva-bo['gpu_va']; d=bo['data']; bosz=bo['size']
    T=1
    while (T*2)*(T*2)*bpp<=0x4000: T*=2
    G=max(1,0x4000//(T*T*bpp)); D=int(round(math.log2(T)))
    print(f"# {label}: fmt={fmt} bpp={bpp} {W}x{H} mips={M} T={T} G={G} BO=0x{bosz:x} base_off=0x{base:x}")

    # per-level padded sizes + cumulative offsets.
    # RULE (EXP-M4-07): the small-mip TAIL — the run beginning at the first level whose
    # levelBytes <= 0x8000 (2 pages) — starts at an offset aligned UP to 0x8000. Pow2 bases
    # are already aligned (no gap); non-pow2 insert one extra 0x4000 page.
    TAIL_ALIGN=0x8000
    offs=[]; cum=0; tail_started=False
    for L in range(M):
        lw=max(1,W>>L); lh=max(1,H>>L)
        pw=pad_axis_w(lw,T,G); ph=pad_axis_h(lh,T)
        lb=max(pw*ph*bpp,0x80)
        if (not tail_started) and lb<=TAIL_ALIGN:
            tail_started=True
            cum=(cum+TAIL_ALIGN-1)//TAIL_ALIGN*TAIL_ALIGN   # align tail start
        offs.append((L,lw,lh,pw,ph,lb,cum)); cum+=lb
    total=cum
    # check every texel of every level
    miss=0; permiss=[0]*M
    for L,lw,lh,pw,ph,lb,off in offs:
        cols=pw//T
        for y in range(lh):
            for x in range(lw):
                tx,ty=x>>D,y>>D
                e=(ty*cols+tx)*(T*T)+morton(x&(T-1),y&(T-1),D)
                boff=base+off+e*bpp
                eb=expect_bytes(fmt,x,y,L)  # tag=L
                if boff+len(eb)>len(d) or d[boff:boff+len(eb)]!=eb:
                    miss+=1; permiss[L]+=1
    print(f"#  {'L':>2} {'lw':>4} {'lh':>4} {'padW':>5} {'padH':>5} {'levelBytes':>10} {'offset':>9} {'permiss':>7}")
    for (L,lw,lh,pw,ph,lb,off) in offs:
        print(f"#  {L:>2} {lw:>4} {lh:>4} {pw:>5} {ph:>5} 0x{lb:08x} 0x{off:07x} {permiss[L]:>7}")
    print(f"# total predicted = 0x{total:x}  BO=0x{bosz:x}  {'(matches)' if total==bosz else '(DIFFERS)'}")
    print(f"# TOTAL mismatch across all levels = {miss}  {'<== MODEL CONFIRMED' if miss==0 else ''}")
    return 0
if __name__=='__main__': sys.exit(main())
