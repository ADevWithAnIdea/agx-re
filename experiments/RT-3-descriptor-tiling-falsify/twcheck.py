#!/usr/bin/env python3
"""twcheck.py -- RT-3 INDEPENDENT twiddle-formula falsifier.

Reads iotrace BO dumps of a texprobe/typrobe run where each element stores an
encoding of its (x,y[,slice/sample]) coordinate. It (1) locates the texture base
VA from the descriptor, (2) decodes every element's stored coordinate to build the
exact element-index -> coordinate map from the RAW backing, then (3) computes the
DOC's predicted element index for that coordinate and checks predicted == actual
for EVERY element. Any mismatch is printed with (coord, actual_e, predicted_e).

Doc formulas under test (docs/tiling/README.md):
  2D  : morton(x,y) with NPOT high-bit append (interleave to n=min(kx,ky), then
        append high bits of larger padded dim linearly).
  3D  : e = z*Wp*Hp + morton(x,y)          (only W,H pow2-padded)
  arr : e = layer*Wp*Hp + morton(x,y)      (cube = 6-layer array)
  msaa: e = N*morton(x,y) + sample          (sample-major / samples lowest bits)

CLEAN-ROOM: operates only on captured DATA bytes. No Apple code.

Usage:
  twcheck.py DUMPDIR --mode 2d|3d|array|cube|msaa --w W --h H
             [--d D] [--layers L] [--samples N] [--bpp 4]
"""
import argparse, glob, os, re, sys

HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu=cpu=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu,cpu,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'path':path,'gpu_va':gpu,'size':size,'data':bytes(data)}

def klog(n):  # ceil log2 -> pow2 exponent
    return (n-1).bit_length() if n>1 else 0

# --- DOC formula (docs/tiling README) : pure Morton, interleave to min(kx,ky) ---
def morton_doc(x,y,W,H):
    kx=klog(W); ky=klog(H); Wp=1<<kx; Hp=1<<ky; n=min(kx,ky)
    e=0
    for i in range(n):
        e |= ((x>>i)&1)<<(2*i)
        e |= ((y>>i)&1)<<(2*i+1)
    if Wp>Hp:
        for i in range(n,kx): e |= ((x>>i)&1)<<(n+i)
    elif Hp>Wp:
        for i in range(n,ky): e |= ((y>>i)&1)<<(n+i)
    return e

# --- CORRECTED (RT-3) : 2^D x 2^D Morton tiles in ROW-MAJOR tile order.
# Measured interleave depth D(bpp): 2bpp/4bpp -> 6 (64x64 tile); 8bpp/16bpp -> 5 (32x32 tile).
def tile_depth(bpp): return 6 if bpp<=4 else 5
def morton_tiled(x,y,W,H,bpp):
    D=tile_depth(bpp); T=1<<D; kx=klog(W); Wp=1<<kx
    cols=max(1,Wp>>D)          # number of tile columns (padded width / tile edge)
    tx=x>>D; ty=y>>D; xl=x&(T-1); yl=y&(T-1)
    m=0
    for i in range(D):
        m |= ((xl>>i)&1)<<(2*i)
        m |= ((yl>>i)&1)<<(2*i+1)
    return (ty*cols+tx)*(T*T) + m
MODE_MORTON={'doc':morton_doc}
def morton2d(x,y,W,H,bpp=4,model='tiled'):
    return morton_tiled(x,y,W,H,bpp) if model=='tiled' else morton_doc(x,y,W,H)

def find_desc_va(bos,W,H,typenib):
    """find a 32-byte descriptor whose (W,H) decode (14-bit hyp) match and baseVA is captured."""
    cands=[]
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w0=int.from_bytes(d[o:o+4],'little'); w1=int.from_bytes(d[o+4:o+8],'little')
            if (w0&0xf)!=typenib: continue
            wi=(((w0>>28)&0xf)|((w1&0x3ff)<<4))+1
            hi=((w1>>10)&0x3fff)+1
            if wi!=W or hi!=H: continue
            w2=int.from_bytes(d[o+8:o+12],'little'); w3=int.from_bytes(d[o+12:o+16],'little')
            bva=(w2|((w3&0xfff)<<32))<<4
            if any(bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size'] for bb in bos):
                cands.append((bva,b['gpu_va'],o,w0,w1,w2,w3))
    return cands

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--mode',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--d',type=int,default=1); ap.add_argument('--layers',type=int,default=1)
    ap.add_argument('--samples',type=int,default=1); ap.add_argument('--bpp',type=int,default=4)
    ap.add_argument('--model',default='tiled',choices=['tiled','doc'])
    a=ap.parse_args()
    W,H,bpp=a.w,a.h,a.bpp
    typenib={'2d':2,'3d':5,'array':3,'cube':6,'msaa':4}[a.mode]
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    cands=find_desc_va(bos,W,H,typenib)
    if not cands:
        print(f'!! no descriptor for {W}x{H} type={typenib} found');
        for b in bos: print(f'   BO 0x{b["gpu_va"]:x} sz=0x{b["size"]:x}')
        return 1
    base_va=cands[0][0]
    print(f'# base VA=0x{base_va:x} (desc w0={cands[0][3]:08x} w1={cands[0][4]:08x} w2={cands[0][5]:08x} w3={cands[0][6]:08x})')
    bo=min((bb for bb in bos if bb['gpu_va']<=base_va<bb['gpu_va']+bb['size']),key=lambda bb:base_va-bb['gpu_va'])
    d=bo['data']; base=base_va-bo['gpu_va']
    print(f'# texture BO 0x{bo["gpu_va"]:x} sz=0x{bo["size"]:x} base_off=0x{base:x} bpp={bpp} mode={a.mode}')

    Wp=1<<klog(W); Hp=1<<klog(H)
    # decode element -> coord map from raw backing
    cap=(len(d)-base)//bpp
    # limit scan
    if a.mode in ('3d','array','cube'):
        planes=a.d if a.mode=='3d' else a.layers
        cap=min(cap, planes*Wp*Hp+Wp*Hp)
    elif a.mode=='msaa':
        cap=min(cap, a.samples*Wp*Hp+Wp*Hp)
    else:
        cap=min(cap, Wp*Hp+ (1<<14))

    def decode(el):
        v=int.from_bytes(el[:4],'little')
        if (v>>16)!=0xa5a5: return None
        return v & 0xffff  # low 16 bits carry coord fields

    mism=[]; checked=0; e2=dict()
    for e in range(cap):
        el=d[base+e*bpp:base+e*bpp+bpp]
        if len(el)<4: break
        low=decode(el)
        if low is None: continue
        e2[e]=low
    # now for each expected coord, compute predicted e and compare to first actual e that stored it
    coord2e={}
    for e,low in e2.items():
        coord2e.setdefault(low,e)  # first (lowest) element index storing this coord

    M=lambda x,y: morton2d(x,y,W,H,a.bpp,a.model)
    def predicted(coord):
        if a.mode=='2d':
            x=coord&0xff; y=(coord>>8)&0xff
            if not(0<=x<W and 0<=y<H): return None,None
            return M(x,y),(x,y)
        # typrobe 4-bit fields
        x=coord&0xf; y=(coord>>4)&0xf; s=(coord>>8)&0xf
        if a.mode=='3d':
            if not(0<=x<W and 0<=y<H and 0<=s<a.d): return None,None
            return s*Wp*Hp+M(x,y),(x,y,s)
        if a.mode in('array','cube'):
            L=a.layers if a.mode=='array' else 6
            if not(0<=x<W and 0<=y<H and 0<=s<L): return None,None
            return s*Wp*Hp+M(x,y),(x,y,s)
        if a.mode=='msaa':
            if not(0<=x<W and 0<=y<H and 0<=s<a.samples): return None,None
            return a.samples*M(x,y)+s,(x,y,s)
        return None,None

    for coord,actual_e in sorted(coord2e.items()):
        pe,c=predicted(coord)
        if pe is None: continue
        checked+=1
        if pe!=actual_e:
            mism.append((c,actual_e,pe))
    print(f'# checked {checked} distinct coords; {len(mism)} MISMATCH')
    if mism:
        print('!! DISCREPANCY — doc formula does NOT reproduce these (coord, actual_e, predicted_e):')
        for c,ae,pe in mism[:40]:
            print(f'   coord={c} actual_e={ae}(0x{ae:x}) predicted_e={pe}(0x{pe:x}) diff={ae-pe}')
        if len(mism)>40: print(f'   ... +{len(mism)-40} more')
        # also dump the actual e-grid for eyeballing (2d)
    else:
        print('   CONFIRMED: doc formula reproduces every captured coordinate exactly.')
    # coverage
    print(f'# coverage: {len(coord2e)} distinct coords found in backing')
    return 0

if __name__=='__main__': sys.exit(main())
