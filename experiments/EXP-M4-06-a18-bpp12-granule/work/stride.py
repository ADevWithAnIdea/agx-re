#!/usr/bin/env python3
"""stride.py — MODEL-INDEPENDENT tile-stride reading for r16uint texprobe captures.

The texprobe r16 kernel writes texel(x,y) = ((y&0xff)<<8)|(x&0xff). For anchor
texels at tile origins (0,0),(T,0),(0,T),... the stored value first appears in
the backing BO exactly at that tile's element index (earlier elements belong to
tile-row 0 / tile-col 0 and cannot alias the anchor's byte pattern). So the FIRST
element index whose stored u16 == anchor value directly reveals:
    tile-col stride = e(T,0)-e(0,0)  (== T^2, confirms tile edge T)
    tile-row stride = e(0,T)-e(0,0)  (== cols*T^2  =>  cols)
This assumes ONLY that the Morton within-tile order maps (0,0)->offset 0 (true for
any Morton), NOT any particular cols-padding rule. Clean-room: DATA bytes only.

Usage: stride.py DUMPDIR --w 320 --h 320 [--t 64]
"""
import argparse, glob, os, re, sys
HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

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

def find_desc(bos,W,H):
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(4)]
            if (w[0]&7)!=2: continue
            width=(((w[0]>>28)&0xf)|((w[1]&0x3ff)<<4))+1
            height=((w[1]>>10)&0x3fff)+1
            if width==W and height==H:
                bva=(w[2]|((w[3]&0xfff)<<32))<<4
                if any(bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size'] for bb in bos):
                    return bva
    return None

def anchor_val(x,y): return ((y&0xff)<<8)|(x&0xff)   # r16 kernel encoding

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dumpdir')
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--t',type=int,default=64)
    a=ap.parse_args(); W=a.w; H=a.h; T=a.t; bpp=2
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    bva=find_desc(bos,W,H)
    if bva is None: print(f'# {a.dumpdir}: descriptor {W}x{H} not found'); return 1
    bo=min((b for b in bos if b['gpu_va'] and b['gpu_va']<=bva<b['gpu_va']+b['size']),
           key=lambda b: bva-b['gpu_va'])
    base=bva-bo['gpu_va']; d=bo['data']; n=(min(len(d),bo['size'])-base)//bpp
    # first element index whose stored u16 == anchor value
    def first_e(val):
        for e in range(n):
            o=base+e*bpp
            if int.from_bytes(d[o:o+2],'little')==val: return e
        return None
    anchors=[(0,0),(T,0),(0,T),(2*T,0),(0,2*T),(3*T,0),(4*T,0),(5*T,0),(6*T,0)]
    print(f"# {a.dumpdir} {W}x{H} bpp=2 T={T} BOsz=0x{bo['size']:x} base_off=0x{base:x} nelem={n}")
    e00=first_e(anchor_val(0,0))
    for (x,y) in anchors:
        if x>=W or y>=H: continue
        e=first_e(anchor_val(x,y))
        print(f"  e({x:4d},{y:4d}) = {e}")
    eT0=first_e(anchor_val(T,0)); e0T=first_e(anchor_val(0,T))
    if e00 is not None and eT0 is not None:
        cs=eT0-e00; print(f"# tile-col stride e({T},0)-e(0,0) = {cs}  (T^2={T*T} => {'T='+str(T)+' OK' if cs==T*T else 'MISMATCH'})")
    if e00 is not None and e0T is not None:
        rs=e0T-e00; print(f"# tile-row stride e(0,{T})-e(0,0) = {rs}  => cols = {rs/(T*T):.3f}")
    return 0
if __name__=='__main__': sys.exit(main())
