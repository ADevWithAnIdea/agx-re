#!/usr/bin/env python3
"""ccheck.py -- RT-3 lossless-compression falsifier.

For a sampled (no-ShaderWrite) texture that should be compressible, decodes the
descriptor and checks: word1.b27 (comp aux) / word3.b31 (aux meta) set, secondary
VA = baseVA + paddedImageBytes, and aux size = imageBytes/128 (inferred from the
backing BO total size). Computes paddedImageBytes independently from W,H,bpp[,mips].
Also usable to check the >=16x16 enable threshold (expect_comp 0/1).

CLEAN-ROOM: DATA only.
Usage: ccheck.py DUMPDIR --w W --h H --bpp B [--mips N] [--type 2d] [--expect-comp 1]
"""
import argparse, glob, os, re, sys
HEXLINE=re.compile(r'^([0-9a-f]{8}):\s+(.*)$'); HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
def load(path):
    gpu=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu,_,size=(int(m.group(i),16) for i in(1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'gpu_va':gpu,'size':size,'data':bytes(data)}
def np2(n): return 1<<((n-1).bit_length()) if n>1 else 1
def padded_image_bytes(W,H,bpp,mips):
    tot=0
    for L in range(mips):
        lw=max(1,W>>L); lh=max(1,H>>L)
        b=np2(lw)*np2(lh)*bpp
        tot+= max(b,0x80) if mips>1 else b
    return tot
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dumpdir')
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--bpp',type=int,required=True); ap.add_argument('--mips',type=int,default=1)
    ap.add_argument('--type',default='2d'); ap.add_argument('--expect-comp',type=int,default=1)
    a=ap.parse_args()
    typenib={'2d':2,'3d':5,'array':3,'cube':6}[a.type]
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    # find sampled descriptor (14-bit W/H) matching
    desc=None
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w0=int.from_bytes(d[o:o+4],'little'); w1=int.from_bytes(d[o+4:o+8],'little')
            if (w0&0xf)!=typenib: continue
            wi=(((w0>>28)&0xf)|((w1&0x3ff)<<4))+1; hi=((w1>>10)&0x3fff)+1
            if wi!=a.w or hi!=a.h: continue
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(8)]
            bva=(w[2]|((w[3]&0xfff)<<32))<<4
            if any(bb['gpu_va']<=bva<bb['gpu_va']+bb['size'] for bb in bos):
                desc=(w,bva); break
        if desc: break
    if not desc: print(f'!! descriptor {a.w}x{a.h} not found'); return 1
    w,bva=desc
    comp=(w[1]>>27)&1; auxmeta=(w[3]>>31)&1
    sec=(w[4]|((w[5]&0xfff)<<32))<<4
    imgb=padded_image_bytes(a.w,a.h,a.bpp,a.mips)
    print(f'# desc words: '+' '.join(f'{x:08x}' for x in w))
    print(f'# baseVA=0x{bva:x} comp(w1.b27)={comp} auxmeta(w3.b31)={auxmeta} secondaryVA=0x{sec:x}')
    print(f'# expected paddedImageBytes=0x{imgb:x} (W={a.w} H={a.h} bpp={a.bpp} mips={a.mips})')
    np=[0,0]
    def chk(n,g,e):
        ok=g==e; np[0]+=1; np[1]+=ok; print(f'  {"PASS" if ok else "FAIL"} {n}: got={g} exp={e}')
    chk('comp aux present (w1.b27)',comp,a.expect_comp)
    if a.expect_comp:
        chk('aux meta (w3.b31)',auxmeta,1)
        chk('secondaryVA == baseVA+imageBytes', hex(sec), hex(bva+imgb))
        # aux size from BO total
        bo=next((bb for bb in bos if bb['gpu_va']<=bva<bb['gpu_va']+bb['size']),None)
        if bo:
            bosz=bo['size']; off=bva-bo['gpu_va']; region=bosz-off
            print(f'  INFO backing BO 0x{bo["gpu_va"]:x} size=0x{bosz:x} region_after_base=0x{region:x} '
                  f'imageBytes=0x{imgb:x} aux=region-image=0x{region-imgb:x} exp_aux~image/128=0x{imgb//128:x}')
    else:
        chk('no comp aux (w1.b27==0)',comp,0)
    print(f'# SUMMARY {np[1]}/{np[0]} PASS')
    return 0
if __name__=='__main__': sys.exit(main())
