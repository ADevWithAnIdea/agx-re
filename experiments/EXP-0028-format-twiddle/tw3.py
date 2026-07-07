#!/usr/bin/env python3
"""tw3.py -- EXP-0028 twiddle solver for array/cube/3D/MSAA layouts.

Reads iotrace BO dumps of a typrobe run where element (x,y,slice) stores
value 0xA5A5<<16 | slice<<8 | y<<4 | x  (r32uint). Locates the texture backing
BO (the one dense with the 0xA5A5 tag), maps physical element index
e = (offset - base)/4 -> (x,y,slice), then:
  * prints the per-slice element-index grid,
  * solves e as a GF(2) function of x-bits / y-bits / slice-bits,
  * reports slice stride and whether slices are LINEAR-STACKED (each slice a
    Morton plane at slice*planeElems) or INTERLEAVED into the Morton curve.

CLEAN-ROOM: operates only on captured DATA bytes. No Apple code.

Usage: tw3.py DUMPDIR --w W --h H --slices N [--label NAME]
"""
import argparse, glob, os, re, sys, math

HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

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

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

def self_ref_descs(bos):
    """all texture descriptors reachable via +0x14a0 self-ref; return list of (base_va,w0..)."""
    out=[]
    for b in bos:
        d=b['data']
        if len(d)<0x14a8: continue
        p=u64(d,0x14a0)
        if b['gpu_va'] and b['gpu_va']<=p<b['gpu_va']+b['size']:
            o=p-b['gpu_va']
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(8)]
            base=(w[2]|((w[3]&0xfff)<<32))<<4
            out.append((base,w))
    return out

def count_tag(d):
    c=0
    for o in range(0,len(d)-4,4):
        if d[o+2]==0xa5 and d[o+3]==0xa5: c+=1
    return c

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--w',type=int,required=True)
    ap.add_argument('--h',type=int,required=True); ap.add_argument('--slices',type=int,required=True)
    ap.add_argument('--label',default=None)
    a=ap.parse_args()
    W,H,S=a.w,a.h,a.slices; bpp=4
    label=a.label or os.path.basename(a.dumpdir.rstrip('/'))
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    if not bos: print(f'{label}: no dumps'); return 1

    # backing BO = the one densest in the 0xA5A5 tag
    tagged=sorted(((count_tag(b['data']),b) for b in bos), key=lambda t:-t[0])
    ntag,bo=tagged[0]
    if ntag < (W*H*S)//2:
        print(f'{label}: tag-sparse (only {ntag} tagged words) — pattern write may have failed')
    # base VA from a descriptor landing in this BO, else BO start
    base_va=None
    for bv,w in self_ref_descs(bos):
        if bo['gpu_va']<=bv<bo['gpu_va']+bo['size']:
            base_va=bv; desc=w; break
    if base_va is None:
        base_va=bo['gpu_va']; desc=None
    base=base_va-bo['gpu_va']
    d=bo['data']
    print(f"# {label}: backing BO 0x{bo['gpu_va']:x} sz=0x{bo['size']:x} base_off=0x{base:x} "
          f"tagged={ntag} expect={W*H*S}")
    if desc:
        print(f"# desc words: "+" ".join(f"{x:08x}" for x in desc)
              +f"  type={desc[0]&0xf} depth/arr field=0x{(desc[3]>>14)&0x1ffff:x}")

    # map (x,y,s) -> first element index
    cap=(len(d)-base)//bpp
    xyz2e={}
    for e in range(cap):
        o=base+e*bpp
        if d[o+2]!=0xa5 or d[o+3]!=0xa5: continue
        v=int.from_bytes(d[o:o+4],'little')
        x=v&0xf; y=(v>>4)&0xf; s=(v>>8)&0xf
        if x>=W or y>=H or s>=S: continue
        xyz2e.setdefault((x,y,s),e)
    cov=len(xyz2e)
    print(f"# coverage {cov}/{W*H*S}")
    if cov==0: print(f"{label}: NO tagged texels decoded"); return 1

    # per-slice element grid (top-left up to 8x8)
    gx=min(8,W); gy=min(8,H)
    for s in range(min(S,8)):
        base_e = xyz2e.get((0,0,s))
        print(f"\n## slice s={s} element index e (top-left {gx}x{gy}), e0={base_e}:")
        print("     "+"".join(f"{x:6d}" for x in range(gx)))
        for y in range(gy):
            print(f"y={y:2d} "+"".join((f"{xyz2e[(x,y,s)]:6d}" if (x,y,s) in xyz2e else "     .") for x in range(gx)))

    # slice stride: e(0,0,s) differences
    e00=[xyz2e.get((0,0,s)) for s in range(S)]
    print(f"\n## e(0,0,s) for s=0..{S-1}: {e00}")
    if all(v is not None for v in e00) and S>1:
        diffs=[e00[s+1]-e00[s] for s in range(S-1)]
        print(f"## slice strides (elements): {diffs}")

    # GF(2) solve: e as fn of x-bits,y-bits,s-bits
    kx=max(1,(W-1).bit_length()); ky=max(1,(H-1).bit_length()); ks=max(1,(S-1).bit_length())
    inputs=[('x',i) for i in range(kx)]+[('y',i) for i in range(ky)]+[('s',i) for i in range(ks)]
    def bit(name,i,x,y,s): return ((x if name=='x' else y if name=='y' else s)>>i)&1
    samples=list(xyz2e.items())
    nb=max(e for _,e in samples).bit_length()
    terms=[]
    ok=True
    for b in range(nb):
        found=None
        for (nm,i) in inputs:
            if all(((e>>b)&1)==bit(nm,i,x,y,s) for (x,y,s),e in samples):
                found=(nm,i); break
        if found is None:
            if all(((e>>b)&1)==0 for _,e in samples): found=('0',0)
            else: found=('?',b); ok=False
        terms.append(found)
    expr=" | ".join(f"{nm}{i}<<{b}" for b,(nm,i) in enumerate(terms) if nm in('x','y','s'))
    print(f"\n## GF(2) element_index = {expr}")
    print(f"## solved-cleanly={ok}  (kx={kx} ky={ky} ks={ks}, {len(samples)} samples)")
    # interpret: are slice bits contiguous high bits (stacked) or interleaved?
    sbits=[b for b,(nm,i) in enumerate(terms) if nm=='s']
    xybits=[b for b,(nm,i) in enumerate(terms) if nm in('x','y')]
    if sbits:
        stacked = min(sbits) > max(xybits) if xybits else True
        print(f"## slice-bit output positions {sbits}; x/y output positions {xybits}")
        print(f"## => slices are {'LINEAR-STACKED (planes)' if stacked else 'INTERLEAVED into Morton'}")
    return 0

if __name__=='__main__':
    sys.exit(main())
