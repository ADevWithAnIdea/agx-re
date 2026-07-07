#!/usr/bin/env python3
"""c_analyze.py -- RT-12 Part C: verify the tiled-Morton layout + tile-multiple padding
from a raw iotrace BO dump of a marker-written texture.

Reconstructs each sampled texel's byte offset under BOTH models:
  cols_tilemult = ceil(W/T)          (docs/tiling RT-9 corrected model)
  cols_nextpow2 = nextpow2(W)/T      (the retracted RT-3 model)
and reports which one the raw bytes actually agree with (0-mismatch = confirmed).

Usage: c_analyze.py DUMPDIR --fmt r32uint|rg32uint --w W --h H
"""
import sys, os, glob, re, argparse

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu_va=cpu=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu_va,cpu,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return dict(path=path,gpu_va=gpu_va,cpu=cpu,size=size,data=bytes(data))

def nextpow2(n):
    p=1
    while p<n: p<<=1
    return p

def morton(a,b,D):
    e=0
    for i in range(D):
        e |= ((a>>i)&1)<<(2*i)
        e |= ((b>>i)&1)<<(2*i+1)
    return e

def elem_index(x,y,T,cols):
    D=T.bit_length()-1
    tx=x//T; ty=y//T
    return (ty*cols+tx)*(T*T) + morton(x&(T-1),y&(T-1),D)

def marker_r32(x,y):  return (0xA0000000 | ((y&0x3fff)<<14) | (x&0x3fff)) & 0xffffffff
def marker_rg32(x,y): return ((0xB0000000|x)&0xffffffff, (0xC0000000|y)&0xffffffff)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--fmt',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    a=ap.parse_args()
    W,H=a.w,a.h
    if a.fmt=='r32uint': bpp=4; isRG=False
    elif a.fmt=='rg32uint': bpp=8; isRG=True
    else: print("unknown fmt"); return 2
    T=64 if bpp<=4 else 32
    cols_tm=(W+T-1)//T
    cols_np=nextpow2(W)//T
    padW_tm=cols_tm*T; padH_tm=((H+T-1)//T)*T
    alloc_tm=padW_tm*padH_tm*bpp
    alloc_np=nextpow2(W)*nextpow2(H)*bpp

    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    print(f"# fmt={a.fmt} W={W} H={H} bpp={bpp} T={T}")
    print(f"# cols_tilemult=ceil(W/T)={cols_tm}  cols_nextpow2=nextpow2(W)/T={cols_np}")
    print(f"# alloc_tilemult=0x{alloc_tm:x}  alloc_nextpow2=0x{alloc_np:x}")

    # find the texture BO: the one whose size best matches EITHER model and that contains our markers
    def count_markers(data):
        c=0
        for (x,y) in [(0,0),(1,0),(0,1),(5,70),(100,200),(W-1,H-1)]:
            if isRG:
                r,_=marker_rg32(x,y); nb=r.to_bytes(4,'little')
            else:
                nb=marker_r32(x,y).to_bytes(4,'little')
            if nb in data: c+=1
        return c
    cand=[b for b in bos if count_markers(b['data'])>=3]
    print(f"# candidate texture BOs (>=3 markers found): {[hex(b['gpu_va'])+' size=0x%x'%b['size'] for b in cand]}")
    if not cand:
        print("FAIL: no texture BO with markers found"); return 1
    # pick the largest candidate (the image itself)
    tex=max(cand,key=lambda b:b['size'])
    data=tex['data']
    print(f"# picked BO gpu_va=0x{tex['gpu_va']:x} registered_size=0x{tex['size']:x} read=0x{len(data):x}")
    print(f"# registered_size matches: tilemult={tex['size']==alloc_tm} nextpow2={tex['size']==alloc_np}")

    # Reconstruct a broad set of texels under BOTH cols models, count mismatches.
    import itertools
    xs=list(range(0,W,max(1,W//24)))+[W-1]
    ys=list(range(0,H,max(1,H//24)))+[H-1]
    for label,cols,padW,padH in [("tilemult",cols_tm,padW_tm,padH_tm),
                                 ("nextpow2",cols_np,nextpow2(W),nextpow2(H))]:
        mm=0; ok=0; checked=0; examples=[]
        for x in xs:
            for y in ys:
                ei=elem_index(x,y,T,cols)
                boff=ei*bpp
                if boff+bpp>len(data): continue
                checked+=1
                if isRG:
                    r,g=marker_rg32(x,y)
                    gotr=int.from_bytes(data[boff:boff+4],'little')
                    gotg=int.from_bytes(data[boff+4:boff+8],'little')
                    good=(gotr==r and gotg==g)
                else:
                    got=int.from_bytes(data[boff:boff+4],'little')
                    good=(got==marker_r32(x,y))
                if good: ok+=1
                else:
                    mm+=1
                    if len(examples)<4: examples.append((x,y,hex(boff)))
        print(f"MODEL {label}: cols={cols} checked={checked} match={ok} mismatch={mm}"
              + (f"  e.g.{examples}" if examples else ""))
    return 0

if __name__=='__main__': sys.exit(main())
