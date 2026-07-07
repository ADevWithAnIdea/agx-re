#!/usr/bin/env python3
"""t9tiling.py -- RT-9 INDEPENDENT tiling solver (2nd red-team pass).

Re-derives the texel(x,y) -> element-index map straight from the RAW backing bytes and:
  (1) solves it as a GF(2) bit-permutation WITHOUT assuming any tile size or the doc formula
      (each output bit is matched to a single input bit x_i/y_i or constant, else NON-PERM);
  (2) DERIVES the tile edge T purely from where the low-bit x0,y0,x1,y1,... interleave breaks
      -> D = interleave depth, T = 2^D; and classifies the high bits (row-major tiles = x-high
      then y-high  vs  full Morton = still interleaved);
  (3) INDEPENDENTLY reconstructs every texel from the recovered permutation (0 mismatch = the
      raw layout IS exactly a permutation) AND, separately, scores the DOC's tiled-Morton
      formula (T=64 bpp<=4 / T=32 bpp>=8) so we can say whether the doc reproduces.

No Apple code. Operates only on captured DATA bytes. Distinct implementation from RT-3.

Usage: t9tiling.py DUMPDIR --fmt <fmt> --w W --h H [--type 2d]
"""
import argparse, glob, os, re, struct, sys

HEX=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
BPP={'r8uint':1,'r16uint':2,'r32uint':4,'rgba8uint':4,'rgba8unorm':4,
     'rg32uint':8,'rgba16uint':8,'rgba16float':8,'rgba32uint':16,'r32float':4}

def load(p):
    gpu=cpu=size=0; data=bytearray()
    for line in open(p):
        if line.startswith('#'):
            m=HDR.search(line)
            if m: gpu,cpu,size=(int(m.group(i),16) for i in (1,2,3))
            continue
        m=HEX.match(line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return {'gpu':gpu,'size':size,'data':bytes(data),'path':p}

def nextpow2(n): return 1<<((n-1).bit_length()) if n>1 else 1

def half(b): return struct.unpack('<e',b)[0]

def decode(fmt, el, W, H):
    """return (x,y) real-texel coordinate or None."""
    if fmt=='r32uint':
        v=int.from_bytes(el[:4],'little')
        if (v>>28)!=0xA: return None
        return (v&0x3fff,(v>>14)&0x3fff)
    if fmt in ('rgba8uint','rgba8unorm'):
        x=el[0]|(el[1]<<8); y=el[2]|(el[3]<<8); return (x,y)
    if fmt=='rg32uint':
        return (int.from_bytes(el[0:4],'little'),int.from_bytes(el[4:8],'little'))
    if fmt=='rgba16uint':
        if int.from_bytes(el[4:6],'little')!=0xBEEF: return None
        return (int.from_bytes(el[0:2],'little'),int.from_bytes(el[2:4],'little'))
    if fmt=='rgba16float':
        try:
            t2=half(el[4:6])
        except Exception: return None
        if not (5000.0 < t2 < 15000.0): return None  # half-rounded tag ~9992 (from 9999.0)
        return (int(round(half(el[0:2]))), int(round(half(el[2:4]))))
    if fmt=='rgba32uint':
        if int.from_bytes(el[8:12],'little')!=0xCAFEBABE: return None
        return (int.from_bytes(el[0:4],'little'),int.from_bytes(el[4:8],'little'))
    if fmt=='r16uint':
        v=int.from_bytes(el[:2],'little'); return (v&0xff,(v>>8)&0xff)
    if fmt=='r8uint':
        idx=el[0]  # ambiguous; caller resolves
        return ('idx',idx)
    return None

def find_desc(bos,W,H,typenib=2):
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
            if any(bb['gpu'] and bb['gpu']<=bva<bb['gpu']+bb['size'] for bb in bos):
                w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(8)]
                return (bva,b['gpu'],o,w)
    return None

def solve_perm(xy2e, kx, ky):
    """Match each output bit to a single input bit or constant. Return (bits, nonperm_bits)."""
    S=list(xy2e.items())
    nbits=max(e for _,e in S).bit_length()
    inputs=[('x',i) for i in range(kx)]+[('y',i) for i in range(ky)]
    bits=[]; nonperm=[]
    for b in range(nbits):
        found=None
        for (src,i) in inputs:
            if all( ((e>>b)&1) == ((( xy[0] if src=='x' else xy[1])>>i)&1) for xy,e in S):
                found=(src,i); break
        if found is None and all(((e>>b)&1)==0 for _,e in S): found=('0',0)
        if found is None: nonperm.append(b)
        bits.append(found)
    return bits,nonperm

def derive_T(bits):
    """From bit list, find interleave depth D: largest D s.t. for i<D bit2i=x_i and bit2i+1=y_i.
       Then classify the remaining high bits."""
    D=0
    while 2*D+1 < len(bits):
        a=bits[2*D]; b=bits[2*D+1]
        if a==('x',D) and b==('y',D): D+=1
        else: break
    T=1<<D
    hi=bits[2*D:]
    # classify: row-major tiles -> all x-high first (contiguous x bits >=D), then y-high.
    # full morton -> continues interleaving x,y.
    xhi=[s for s in hi if s and s[0]=='x']
    yhi=[s for s in hi if s and s[0]=='y']
    seq=[s[0] if s else '?' for s in hi]
    # detect if it's x* then y* (row-major) vs interleaved
    joined=''.join(c for c in seq if c in 'xy')
    rowmajor = ('yx' not in joined)  # x's all before y's
    return D,T,seq,rowmajor

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--fmt',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--type',default='2d')
    a=ap.parse_args()
    fmt=a.fmt; W=a.w; H=a.h; bpp=BPP[fmt]
    typenib={'2d':2,'3d':5,'array':3,'cube':6,'ms':4}[a.type]
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    if not bos: print('no dumps'); return 1
    desc=find_desc(bos,W,H,typenib)
    if not desc:
        print(f'!! DESCRIPTOR {W}x{H} type={typenib} NOT FOUND')
        for b in bos: print(f'   BO 0x{b["gpu"]:x} sz=0x{b["size"]:x}')
        return 1
    base_va,_,doff,w=desc
    print(f'# desc w0={w[0]:08x} w1={w[1]:08x} w2={w[2]:08x} w3={w[3]:08x} w4={w[4]:08x} w5={w[5]:08x}')
    print(f'# base VA=0x{base_va:x}  word1.b26(mip)={(w[1]>>26)&1} b27(comp)={(w[1]>>27)&1} word3.b31={(w[3]>>31)&1}')
    bo=min((b for b in bos if b['gpu']<=base_va<b['gpu']+b['size']),key=lambda b:base_va-b['gpu'])
    d=bo['data']; base=base_va-bo['gpu']
    print(f'# tex BO 0x{bo["gpu"]:x} sz=0x{bo["size"]:x} base_off=0x{base:x} fmt={fmt} bpp={bpp} {W}x{H}')

    Wp=nextpow2(W); Hp=nextpow2(H); kx=(W-1).bit_length(); ky=(H-1).bit_length()
    cap=min((len(d)-base)//bpp, Wp*Hp+ (1<<16))
    xy2e={}
    for e in range(cap):
        el=d[base+e*bpp:base+e*bpp+bpp]
        if len(el)<bpp: break
        dec=decode(fmt,el,W,H)
        if dec is None: continue
        if dec[0]=='idx':
            idx=dec[1]  # not used for perm
            continue
        x,y=dec
        if not(0<=x<W and 0<=y<H): continue
        if (x,y) not in xy2e: xy2e[(x,y)]=e
    cov=len(xy2e)
    print(f'# coverage {cov}/{W*H}')
    if cov < W*H:
        print(f'!! INCOMPLETE coverage ({cov}/{W*H}) — cannot fully solve (garbage/padding?)')
    if cov==0: return 1

    # (1)+(2) independent GF(2) solve + derive T
    bits,nonperm=solve_perm(xy2e,kx,ky)
    def fmtbit(s): return '?' if s is None else ('0' if s[0]=='0' else f'{s[0]}{s[1]}')
    print('## recovered bit-permutation e_b[k] = :', ' '.join(f'b{k}={fmtbit(s)}' for k,s in enumerate(bits)))
    if nonperm:
        print(f'!! NON-PERMUTATION at output bits {nonperm} — layout is NOT a pure bit-permutation of (x,y)!')
    D,T,seq,rowmajor=derive_T(bits)
    print(f'## DERIVED (independent of doc): interleave depth D={D} -> tile edge T={T}x{T};'
          f' high-bit order={"".join(seq)} -> {"ROW-MAJOR tiles" if rowmajor else "FULL MORTON (interleaved)"}')

    # (3a) reconstruct from recovered permutation -> must be 0 mismatch (it is a permutation by construction if nonperm empty)
    def predict_recovered(x,y):
        e=0
        for b,s in enumerate(bits):
            if s is None or s[0]=='0': continue
            v=x if s[0]=='x' else y
            e |= (((v>>s[1])&1)<<b)
        return e
    mm_rec=sum(1 for (x,y),e in xy2e.items() if predict_recovered(x,y)!=e)
    print(f'## reconstruct-from-recovered-perm: {mm_rec} mismatch / {cov}')

    # (3b) DOC tiled-Morton formula (T=64 if bpp<=4 else 32), row-major tiles
    Ddoc = 6 if bpp<=4 else 5; Tdoc=1<<Ddoc; cols=max(1,Wp>>Ddoc)
    def predict_doc(x,y):
        tx=x>>Ddoc; ty=y>>Ddoc; xl=x&(Tdoc-1); yl=y&(Tdoc-1); m=0
        for i in range(Ddoc):
            m|=((xl>>i)&1)<<(2*i); m|=((yl>>i)&1)<<(2*i+1)
        return (ty*cols+tx)*(Tdoc*Tdoc)+m
    mm_doc=sum(1 for (x,y),e in xy2e.items() if predict_doc(x,y)!=e)
    print(f'## DOC formula (T={Tdoc}, cols={cols}): {mm_doc} mismatch / {cov}')
    ex=[]
    for (x,y),e in sorted(xy2e.items()):
        if predict_doc(x,y)!=e:
            ex.append((x,y,e,predict_doc(x,y)))
    if ex:
        print('!! DOC MISMATCH examples (x,y,actual_e,doc_e):', ex[:8])

    verdict_T = (T==Tdoc)
    print(f'\n=== VERDICT: derived T={T}, doc-expected T={Tdoc} -> {"MATCH" if verdict_T else "DISCREPANCY"};'
          f' doc formula reproduces raw = {"YES (0 mismatch)" if mm_doc==0 and cov==W*H else "NO"}')
    return 0

if __name__=='__main__': sys.exit(main())
