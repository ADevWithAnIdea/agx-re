#!/usr/bin/env python3
"""twiddle.py -- EXP-0017 texture tiling/twiddle analyzer.

Reads iotrace BO .hex dumps of a texprobe run (texel(x,y) holds encode(x,y)),
locates the texture DESCRIPTOR (anchored on the known dims W-1/H-1 + 2D type),
reads the exact texture base VA from it, finds the backing BO, then maps element
index e = (offset-base)/bpp -> texel (x,y) by decoding each element's stored value.
Because we start at the exact descriptor base, only real texels are read (no garbage).

Infers the tiling/twiddle order:
  * prints the physical element-index grid (eyeball the twiddle);
  * solves (x,y)->element-index as a GF(2) bit permutation (exact formula);
  * reports the descriptor layout flags (word1 bit27 / word3 bit31) + secondary VA.

CLEAN-ROOM: operates only on captured DATA bytes. No Apple code.

Usage:
  twiddle.py DUMPDIR --fmt r32uint --w 64 --h 64 [--grid 32]
"""
import argparse, glob, os, re, sys, math

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

FMT_BPP = {'r8uint':1,'r16uint':2,'r32uint':4,'rg32uint':8,
           'rgba8uint':4,'rgba16uint':8,'rgba32uint':16,'rgba8unorm':4,'r32float':4}

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
    return {'path':path,'gpu_va':gpu_va,'cpu':cpu,'size':size,'data':bytes(data)}

def decode_val(fmt, elem):
    """elem = bytes of one texel -> (x,y) or None if not a valid marker."""
    if fmt=='r8uint':   return ('idx', elem[0])       # value=(y*W+x)&0xff; caller resolves
    if fmt=='r16uint':
        v=int.from_bytes(elem[:2],'little'); return (v&0xff,(v>>8)&0xff)
    if fmt=='r32uint':
        v=int.from_bytes(elem[:4],'little')
        if (v>>16)!=0xa5a5: return None
        return (v&0xff,(v>>8)&0xff)
    if fmt=='rg32uint':
        return (int.from_bytes(elem[0:4],'little'),int.from_bytes(elem[4:8],'little'))
    if fmt=='rgba8uint':
        if elem[2]==0xab and elem[3]==0xcd: return (elem[0],elem[1])
        return None
    if fmt=='rgba16uint':
        if int.from_bytes(elem[4:6],'little')==0xbeef and int.from_bytes(elem[6:8],'little')==0xf00d:
            return (int.from_bytes(elem[0:2],'little'),int.from_bytes(elem[2:4],'little'))
        return None
    if fmt=='rgba32uint':
        if int.from_bytes(elem[8:12],'little')==0xcafebabe and int.from_bytes(elem[12:16],'little')==0xdeadbeef:
            return (int.from_bytes(elem[0:4],'little'),int.from_bytes(elem[4:8],'little'))
        return None
    if fmt=='rgba8unorm':   # render path: B=170(0xaa) A=205(0xcd) tag
        if elem[2]==0xaa and elem[3]==0xcd: return (elem[0],elem[1])
        return None
    return None

def find_descriptor(bos, W, H):
    """Find a 2D texture descriptor whose width-1/height-1 fields == W-1/H-1.
    Returns (bo, off, words) or None."""
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(8)]
            if (w[0]&0x7)!=2: continue
            width  = (((w[0]>>28)&0xf) | ((w[1]&0xff)<<4)) + 1
            height = ((w[1]>>10)&0xfff) + 1
            if width==W and height==H:
                bva=(w[2] | ((w[3]&0xfff)<<32))<<4
                # base VA must land inside some captured BO
                if any(bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size'] for bb in bos):
                    return (b,o,w)
    return None

def solve_bitperm(xy2p, W, H):
    kx=int(math.floor(math.log2(W))); ky=int(math.floor(math.log2(H)))
    Wp=1<<kx; Hp=1<<ky
    S=[(x,y,p) for (x,y),p in xy2p.items() if x<Wp and y<Hp]
    if not S: return None
    nbits=max(p for _,_,p in S).bit_length()
    inputs=[('x',i) for i in range(kx)]+[('y',i) for i in range(ky)]
    bits=[]
    for b in range(nbits):
        m=None
        for (src,i) in inputs:
            if all((((p>>b)&1)==(((x if src=='x' else y)>>i)&1)) for (x,y,p) in S):
                m=(src,i); break
        if m is None and all(((p>>b)&1)==0 for _,_,p in S): m=('0',0)
        bits.append(m)
    return {'kx':kx,'ky':ky,'Wp':Wp,'Hp':Hp,'bits':bits,'n':len(S)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--fmt',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--grid',type=int,default=32)
    a=ap.parse_args()
    fmt=a.fmt; W=a.w; H=a.h; bpp=FMT_BPP[fmt]
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    if not bos: print('no dumps in',a.dumpdir); return 1

    desc=find_descriptor(bos,W,H)
    if not desc:
        print(f'DESCRIPTOR for {W}x{H} not found');
        for b in bos: print(f"  BO va=0x{b['gpu_va']:x} sz=0x{b['size']:x}")
        return 1
    db,doff,w=desc
    base_va=(w[2] | ((w[3]&0xfff)<<32))<<4
    # secondary VA parallels base: word4 (low32) + word5[0:11] (high12), <<4.
    sec=(w[4] | ((w[5]&0xfff)<<32))<<4 if w[4] else 0
    mipm1=(w[5]>>16)&0xf
    # texture BO = one containing base_va with smallest positive offset
    cand=[bb for bb in bos if bb['gpu_va'] and bb['gpu_va']<=base_va<bb['gpu_va']+bb['size']]
    bo=min(cand,key=lambda bb: base_va-bb['gpu_va'])
    base=base_va-bo['gpu_va']
    d=bo['data']
    print(f"# DESCRIPTOR in BO 0x{db['gpu_va']:x}+0x{doff:x}: "
          f"w0={w[0]:08x} w1={w[1]:08x} w2={w[2]:08x} w3={w[3]:08x} "
          f"w4={w[4]:08x} w5={w[5]:08x} w6={w[6]:08x} w7={w[7]:08x}")
    print(f"# base VA=0x{base_va:x}  layout word1.b27={(w[1]>>27)&1} word1.b26(mip)={(w[1]>>26)&1} "
          f"word3.b31={(w[3]>>31)&1}  mipCount-1={mipm1}  secondaryVA=0x{sec:x}"
          + (f"  (=base+0x{sec-base_va:x})" if sec else ""))
    if sec:
        sbo=next((bb for bb in bos if bb['gpu_va'] and bb['gpu_va']<=sec<bb['gpu_va']+bb['size']),None)
        print(f"# secondary VA lands in BO {('0x%x+0x%x'%(sbo['gpu_va'],sec-sbo['gpu_va'])) if sbo else 'NONE'}")
    print(f"# TEXTURE BO va=0x{bo['gpu_va']:x} sz=0x{bo['size']:x} base_off=0x{base:x} fmt={fmt} bpp={bpp} {W}x{H}")

    # map element index e -> (x,y); keep FIRST (lowest offset) per texel
    npot = (1<<((W-1).bit_length())) * (1<<((H-1).bit_length()))
    cap = min(npot*4, (len(d)-base)//bpp)  # generous: padded area x4
    xy2p={}; e2xy={}
    for e in range(cap):
        o=base+e*bpp; el=d[o:o+bpp]
        if len(el)<bpp: break
        dec=decode_val(fmt,el)
        if dec is None: continue
        if fmt=='r8uint':
            idx=dec[1]
            if idx>=W*H: continue
            xy=(idx%W,idx//W)
        else:
            xy=dec
            if not(0<=xy[0]<W and 0<=xy[1]<H): continue
        e2xy.setdefault(e,xy)
        if xy not in xy2p: xy2p[xy]=e
        if len(xy2p)>=W*H and e> max(xy2p.values())+ (1<<12): break
    print(f"# coverage {len(xy2p)}/{W*H}")

    g=min(a.grid,W,H)
    print(f"\n## element index e for texel (x,y), top-left {g}x{g}:")
    print("     "+"".join(f"{x:6d}" for x in range(g)))
    for y in range(g):
        print(f"y={y:3d} "+"".join((f"{xy2p[(x,y)]:6d}" if (x,y) in xy2p else "     .") for x in range(g)))

    sol=solve_bitperm(xy2p,W,H)
    if sol:
        print(f"\n## GF(2) bit-permutation over {sol['Wp']}x{sol['Hp']} block ({sol['n']} samples):")
        print("  "+"  ".join(
            (f"e_b{b}=?" if s is None else (f"e_b{b}=0" if s[0]=='0' else f"e_b{b}={s[0]}{s[1]}"))
            for b,s in enumerate(sol['bits'])))
        terms=[f"{s[0]}{s[1]}<<{b}" for b,s in enumerate(sol['bits']) if s and s[0] in('x','y')]
        print("  element_index = " + " | ".join(terms))
    xs=[x for x,y in xy2p]; ys=[y for x,y in xy2p]
    if xs: print(f"\n## extent x[{min(xs)},{max(xs)}] y[{min(ys)},{max(ys)}]  max_e={max(xy2p.values())}")
    return 0

if __name__=='__main__':
    sys.exit(main())
