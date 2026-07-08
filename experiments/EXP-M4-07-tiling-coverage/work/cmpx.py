#!/usr/bin/env python3
"""cmpx.py — EXP-M4-07 TIL-5/TIL-6 compression descriptor + aux-size analyzer.

For a texprobe --render --usage rt capture, locate the 2D texture descriptor,
report the compression flags (word1 bit27 = aux present, word3 bit31 = aux layout),
the base VA and secondary(aux) VA, and the backing BO total size. Compute the
tile-padded image bytes from the HW-validated 2D rule (T(bpp)+G), then resolve:
    aux_bytes    = totalBO - paddedImageBytes           (tail-of-BO aux region)
    sec - base   (should == paddedImageBytes if aux placed right after image)
    ratio        = aux_bytes / image_bytes   vs formula A(1/128) / B(1/(32*bpp))
Clean-room: captured DATA bytes only. No Apple code.
Usage: cmpx.py DUMPDIR --fmt rgba32f --w 256 --h 256 [--label NAME]
"""
import argparse, glob, os, re, sys
HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
BPP={'rgba8unorm':4,'r32float':4,'rgba16f':8,'rgba32f':16,'r8unorm':1,'r16f':2,'rg16f':4,'rgba16unorm':8,
     'bgra8unorm':4,'r8uint':1,'r16uint':2,'r32uint':4,'rg32uint':8,'rgba32uint':16}

def load(p):
    gpu_va=cpu=size=0; data=bytearray()
    for line in open(p):
        if line.startswith('#'):
            m=HDR.search(line)
            if m: gpu_va,cpu,size=(int(m.group(i),16) for i in (1,2,3))
            continue
        m=HEXLINE.match(line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return {'gpu_va':gpu_va,'cpu':cpu,'size':size,'data':bytes(data)}

def pad2d(W,H,bpp):
    T=1
    while (T*2)*(T*2)*bpp<=0x4000: T*=2
    G=max(1,0x4000//(T*T*bpp))
    def nextpow2(n): return 1<<((n-1).bit_length()) if n>1 else 1
    ntw=-(-W//T)
    cols = ntw if ntw<=1 else ((ntw+G-1)//G)*G
    padW = cols*T if W>=T else nextpow2(W)
    padH = (-(-H//T))*T if H>=T else nextpow2(H)
    return T,G,cols,padW,padH,padW*padH*bpp

def find_desc(bos,W,H):
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(6)]
            if (w[0]&0xf)!=2: continue
            width=(((w[0]>>28)&0xf)|((w[1]&0x3ff)<<4))+1
            height=((w[1]>>10)&0x3fff)+1
            if width!=W or height!=H: continue
            bva=(w[2]|((w[3]&0xfff)<<32))<<4
            if any(bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size'] for bb in bos):
                return bva,w
    return None,None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--fmt',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--label',default=None)
    a=ap.parse_args(); fmt=a.fmt; W=a.w; H=a.h; bpp=BPP[fmt]
    label=a.label or os.path.basename(a.dumpdir.rstrip('/'))
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    bva,w=find_desc(bos,W,H)
    if bva is None: print(f"{label}: descriptor {W}x{H} fmt={fmt} NOT FOUND"); return 1
    bo=min((b for b in bos if b['gpu_va'] and b['gpu_va']<=bva<b['gpu_va']+b['size']),key=lambda b:bva-b['gpu_va'])
    b27=(w[1]>>27)&1; b31=(w[3]>>31)&1
    secVA=(w[4]|((w[5]&0xfff)<<32))<<4
    T,G,cols,padW,padH,imgB=pad2d(W,H,bpp)
    totBO=bo['size']; base_off=bva-bo['gpu_va']
    print(f"# {label}: fmt={fmt} bpp={bpp} {W}x{H}")
    print(f"#   desc: "+" ".join(f"{x:08x}" for x in w))
    print(f"#   word1 bit27(compress)={b27}  word3 bit31(auxmeta)={b31}")
    print(f"#   baseVA=0x{bva:x}  secVA=0x{secVA:x}  backingBO=0x{bo['gpu_va']:x} sz=0x{totBO:x} base_off=0x{base_off:x}")
    print(f"#   2D pad: T={T} G={G} cols={cols} padW={padW} padH={padH} paddedImageBytes=0x{imgB:x} ({imgB})")
    if b27==0 and secVA==0:
        print(f"#   => COMPRESSION NOT ENGAGED (b27=0, secVA=0). BO=0x{totBO:x} vs imgBytes=0x{imgB:x}")
        return 0
    sec_minus_base = secVA-bva
    aux_tail = totBO - base_off - imgB   # aux region = BO tail beyond the image
    print(f"#   secVA-baseVA = 0x{sec_minus_base:x} ({sec_minus_base})  [== paddedImageBytes? {sec_minus_base==imgB}]")
    print(f"#   aux_bytes (BO - base_off - image) = 0x{aux_tail:x} ({aux_tail})")
    ntex=padW*padH
    print(f"#   ratios: aux/imageBytes = 1/{imgB/aux_tail:.1f}   aux/texels = 1/{ntex/aux_tail:.2f}")
    fA=imgB//128; fB=imgB//(32*bpp)
    print(f"#   formula A (imageBytes/128) = 0x{fA:x} ({fA})  {'<-- MATCH' if fA==aux_tail else ''}")
    print(f"#   formula B (1 byte / 8x4 block = imageBytes/(32*bpp)) = 0x{fB:x} ({fB})  {'<-- MATCH' if fB==aux_tail else ''}")
    return 0
if __name__=='__main__': sys.exit(main())
