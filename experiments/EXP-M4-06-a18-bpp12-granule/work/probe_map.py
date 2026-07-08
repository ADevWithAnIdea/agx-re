#!/usr/bin/env python3
"""probe_map.py — invert a texprobe capture: for each element index e in the
backing BO, decode the stored value to (x,y) and record the FIRST e per texel.
Then print the element index of anchor texels so the true tile/row strides are
visible (independent of any assumed model). Clean-room: DATA only.
Usage: probe_map.py DUMPDIR --fmt rg32uint --w 160 --h 96
"""
import argparse, glob, os, re, sys
HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$'); HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
FMT_BPP={'r32uint':4,'rg32uint':8,'rgba16uint':8,'rgba32uint':16,'rgba8uint':4}
def load(p):
    gpu_va=size=0; data=bytearray()
    for line in open(p):
        if line.startswith('#'):
            m=HDR.search(line)
            if m: gpu_va,_,size=(int(m.group(i),16) for i in (1,2,3))
            continue
        m=HEXLINE.match(line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return {'gpu_va':gpu_va,'size':size,'data':bytes(data)}
def dec(fmt,el,W,H):
    if fmt=='r32uint':
        v=int.from_bytes(el[:4],'little')
        if (v>>24)!=0xA5: return None
        x=v&0xfff; y=(v>>12)&0xfff
    elif fmt in('rg32uint','rgba32uint'):
        x=int.from_bytes(el[0:4],'little'); y=int.from_bytes(el[4:8],'little')
    elif fmt=='rgba16uint':
        if el[4:8]!=b'\xef\xbe\x0d\xf0': return None
        x=int.from_bytes(el[0:2],'little'); y=int.from_bytes(el[2:4],'little')
    else: return None
    return (x,y) if 0<=x<W and 0<=y<H else None
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dumpdir'); ap.add_argument('--fmt',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    a=ap.parse_args(); fmt=a.fmt; W=a.w; H=a.h; bpp=FMT_BPP[fmt]
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    # find descriptor for base VA
    bva=None
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(4)]
            if (w[0]&7)!=2: continue
            width=(((w[0]>>28)&0xf)|((w[1]&0x3ff)<<4))+1; height=((w[1]>>10)&0x3fff)+1
            if width==W and height==H:
                cand=(w[2]|((w[3]&0xfff)<<32))<<4
                if any(bb['gpu_va'] and bb['gpu_va']<=cand<bb['gpu_va']+bb['size'] for bb in bos): bva=cand; break
        if bva: break
    bo=min((b for b in bos if b['gpu_va'] and b['gpu_va']<=bva<b['gpu_va']+b['size']),key=lambda b:bva-b['gpu_va'])
    base=bva-bo['gpu_va']; d=bo['data']
    xy2e={}
    n=(bo['size']-base)//bpp
    for e in range(n):
        o=base+e*bpp; xy=dec(fmt,d[o:o+bpp],W,H)
        if xy and xy not in xy2e: xy2e[xy]=e
    print(f"# {a.dumpdir} {W}x{H} bpp={bpp} BOsz=0x{bo['size']:x} coverage={len(xy2e)}/{W*H}")
    T=32
    for anchor in [(0,0),(1,0),(0,1),(T,0),(0,T),(2*T,0),(0,2*T),(3*T,0),(4*T,0),(5*T,0),(W-1,H-1)]:
        e=xy2e.get(anchor)
        print(f"  e({anchor[0]:3d},{anchor[1]:3d}) = {e}")
    # infer col stride from e(T,0)-e(0,0) and row stride from e(0,T)-e(0,0)
    if (T,0) in xy2e and (0,0) in xy2e:
        print(f"# tile-col stride (e(32,0)-e(0,0)) = {xy2e[(T,0)]-xy2e[(0,0)]}  (T^2={T*T})")
    if (0,T) in xy2e and (0,0) in xy2e:
        rs=xy2e[(0,T)]-xy2e[(0,0)]; print(f"# tile-row stride (e(0,32)-e(0,0)) = {rs}  => cols={rs//(T*T)}")
    return 0
if __name__=='__main__': sys.exit(main())
