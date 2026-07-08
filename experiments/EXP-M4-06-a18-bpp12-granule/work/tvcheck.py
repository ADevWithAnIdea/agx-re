#!/usr/bin/env python3
"""tvcheck.py — verify the tiled-Morton twiddle model against a texprobe capture.

For a capture where texel(x,y) holds encode(x,y), locate the texture descriptor +
base VA, load the backing BO, and for EACH candidate model (T, cols-rule) predict
element_index(x,y) = (ty*cols + tx)*T^2 + morton_D(x&(T-1), y&(T-1)), read the stored
value at that byte offset, decode it, and count how many texels match encode(x,y).
The model with 0 mismatches over the full W*H grid is the true layout. This directly
distinguishes cols=ceil(W/T) (RT-9 mult-of-T) from cols=nextpow2(W)/T (RT-3 old).

Clean-room: operates only on captured DATA bytes. No Apple code.
Usage: tvcheck.py DUMPDIR --fmt r32uint --w 384 --h 384
"""
import argparse, glob, os, re, sys, math

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
FMT_BPP = {'r8uint':1,'r16uint':2,'r32uint':4,'rg32uint':8,'rgba8uint':4,
           'rgba16uint':8,'rgba32uint':16,'rgba8unorm':4,'r32float':4}

def load(path):
    gpu_va=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
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

def encode_expect(fmt,x,y):
    """return the bytes texel(x,y) should hold (matching texprobe kernels)."""
    if fmt=='r32uint':   return (0xA5000000|((y&0xfff)<<12)|(x&0xfff)).to_bytes(4,'little')
    if fmt=='r8uint':    return bytes([(x*13+y*29)&0xff])                    # matches texprobe r8 kernel
    if fmt=='r16uint':   return (((y&0xff)<<8)|(x&0xff)).to_bytes(2,'little') # matches texprobe r16 kernel
    if fmt=='rg32uint':  return (x&0xffffffff).to_bytes(4,'little')+(y&0xffffffff).to_bytes(4,'little')
    if fmt=='rgba16uint':return (x&0xffff).to_bytes(2,'little')+(y&0xffff).to_bytes(2,'little')+b'\xef\xbe\x0d\xf0'
    if fmt=='rgba32uint':return (x&0xffffffff).to_bytes(4,'little')+(y&0xffffffff).to_bytes(4,'little')+b'\xbe\xba\xfe\xca\xef\xbe\xad\xde'
    if fmt=='rgba8uint': return bytes([x&0xff,y&0xff,0xab,0xcd])
    return None

def morton(a,b,D):
    r=0
    for i in range(D): r|=((a>>i)&1)<<(2*i) | ((b>>i)&1)<<(2*i+1)
    return r

def find_desc(bos,W,H):
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(6)]
            if (w[0]&0x7)!=2: continue
            width =(((w[0]>>28)&0xf)|((w[1]&0x3ff)<<4))+1
            height=((w[1]>>10)&0x3fff)+1
            if width==W and height==H:
                bva=(w[2]|((w[3]&0xfff)<<32))<<4
                if any(bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size'] for bb in bos):
                    return bva,w
    return None,None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--fmt',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    a=ap.parse_args(); fmt=a.fmt; W=a.w; H=a.h; bpp=FMT_BPP[fmt]
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    bva,w=find_desc(bos,W,H)
    if bva is None: print('descriptor not found'); return 1
    bo=min((b for b in bos if b['gpu_va'] and b['gpu_va']<=bva<b['gpu_va']+b['size']),
           key=lambda b: bva-b['gpu_va'])
    base=bva-bo['gpu_va']; d=bo['data']; bosz=bo['size']
    print(f"# {a.dumpdir} fmt={fmt} {W}x{H} bpp={bpp} baseVA=0x{bva:x} BO=0x{bo['gpu_va']:x} sz=0x{bosz:x} base_off=0x{base:x}")

    def nextpow2(n): return 1<<((n-1).bit_length())
    def cols_corr(W,T,bpp):
        nt=-(-W//T)
        if nt<=1: return nt
        atiles=max(1,0x4000//(T*T*bpp))   # tiles per 16KiB row-stride granule
        return ((nt+atiles-1)//atiles)*atiles
    results=[]
    for T in (32,64,128):
        D=int(math.log2(T))
        for rule,colf in (('ceil(W/T)',lambda W,T:-(-W//T)),
                          ('nextpow2(W)/T',lambda W,T:nextpow2(W)//T),
                          ('16KiB-row',lambda W,T:cols_corr(W,T,bpp))):
            cols=colf(W,T)
            ok=miss=0; maxoff=0
            for y in range(H):
                for x in range(W):
                    tx,ty=x>>D,y>>D
                    e=(ty*cols+tx)*(T*T)+morton(x&(T-1),y&(T-1),D)
                    off=base+e*bpp; maxoff=max(maxoff,off+bpp)
                    exp=encode_expect(fmt,x,y)
                    if off+len(exp)>len(d): miss+=1; continue
                    if d[off:off+len(exp)]==exp: ok+=1
                    else: miss+=1
            results.append((T,rule,cols,ok,miss,maxoff))
    print(f"# {'T':>3} {'cols-rule':<16} {'cols':>4} {'match':>8} {'mismatch':>8} {'maxoff':>8}")
    best=None
    for T,rule,cols,ok,miss,maxoff in results:
        tag=''
        if miss==0:
            tag='  <== MODEL CONFIRMED (0 mismatch)'
            if best is None: best=(T,rule,cols)
        print(f"  {T:>3} {rule:<16} {cols:>4} {ok:>8} {miss:>8} 0x{maxoff:06x}{tag}")
    # allocation-size expectation under confirmed model
    if best:
        T,rule,cols=best
        rows=-(-H//T)
        padW=cols*T if W>=T else nextpow2(W)
        padH=rows*T if H>=T else nextpow2(H)
        print(f"# CONFIRMED: T={T} cols={cols} ({rule}); padW={padW} padH={padH} "
              f"paddedImageBytes=0x{padW*padH*bpp:x} (BO sz=0x{bosz:x})")
    return 0
if __name__=='__main__': sys.exit(main())
