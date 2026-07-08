#!/usr/bin/env python3
"""mipmap.py -- EXP-0017 mip-level packing analyzer.

Reads a texprobe --mips run where each level L was written with a level-tagged
r32uint value 0xB0000000|(L<<24)|((y&0xfff)<<12)|(x&0xfff). Finds the texture BO
(via descriptor, dims = W-1/H-1), scans the region for tagged elements, groups by
level, and reports each level's byte-offset extent (=> per-level base offset and
packing) and the Morton order within each level.

CLEAN-ROOM: captured DATA only. No Apple code.

Usage: mipmap.py DUMPDIR --w 128 --h 128
"""
import argparse, glob, os, re, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twiddle import load, find_descriptor

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    a=ap.parse_args(); W=a.w; H=a.h
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    desc=find_descriptor(bos,W,H)
    if not desc: print('descriptor not found'); return 1
    db,doff,w=desc
    base_va=(w[2]|((w[3]&0xfff)<<32))<<4
    cand=[bb for bb in bos if bb['gpu_va'] and bb['gpu_va']<=base_va<bb['gpu_va']+bb['size']]
    bo=min(cand,key=lambda bb: base_va-bb['gpu_va']); base=base_va-bo['gpu_va']; d=bo['data']
    print(f"# TEXTURE BO 0x{bo['gpu_va']:x} base_off=0x{base:x} sz=0x{bo['size']:x}  {W}x{H}")
    print(f"# descriptor w1=0x{w[1]:08x} (b26 mip={ (w[1]>>26)&1 }, b27={(w[1]>>27)&1})  "
          f"w3=0x{w[3]:08x} (b31={(w[3]>>31)&1})  w5=0x{w[5]:08x} (mipCount-1={(w[5]>>16)&0xf})")
    # scan whole BO from base for tag 0xB elements
    lev={}
    for o in range(base, len(d)-4, 4):
        v=int.from_bytes(d[o:o+4],'little')
        if (v>>28)!=0xB: continue
        L=(v>>24)&0xf; x=v&0xfff; y=(v>>12)&0xfff
        lw=max(1,W>>L); lh=max(1,H>>L)
        if x>=lw or y>=lh: continue
        lev.setdefault(L,{'min':o,'max':o,'n':0,'xy':{}})
        e=lev[L]; e['min']=min(e['min'],o); e['max']=max(e['max'],o); e['n']+=1
        if (x,y) not in e['xy']: e['xy'][(x,y)]=o
    print(f"# levels found: {sorted(lev)}")
    prev=None
    for L in sorted(lev):
        e=lev[L]; lw=max(1,W>>L); lh=max(1,H>>L)
        boff=e['min']-base
        # verify Morton within level for (1,0),(0,1),(1,1) if present
        z=e['xy']
        note=''
        if (0,0) in z and (1,0) in z and (0,1) in z:
            d10=(z[(1,0)]-z[(0,0)])//4; d01=(z[(0,1)]-z[(0,0)])//4
            note=f"  Morton check: (1,0)->e+{d10}, (0,1)->e+{d01} (expect 1 and 2)"
        gap = f"  (prev level end +0x{boff - prev:x})" if prev is not None else ""
        print(f"L{L}: {lw}x{lh}  base_off=0x{boff:x}  span=[0x{e['min']-base:x}..0x{e['max']-base:x}]  "
              f"texels={len(z)}/{lw*lh}{gap}{note}")
        prev = (e['max']-base) + 4
    return 0

if __name__=='__main__':
    sys.exit(main())
