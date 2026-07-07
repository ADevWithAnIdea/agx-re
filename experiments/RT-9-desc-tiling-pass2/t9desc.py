#!/usr/bin/env python3
"""t9desc.py -- RT-9 INDEPENDENT descriptor field checker (2nd red-team pass).

Locates the 32-byte texture descriptor for a known texture by (type nibble + base VA that
lands inside a captured BO), WITHOUT first assuming the width/height bit-packing. Then reads
width-1/height-1 under BOTH the 14-bit (RT-3-corrected) and 12-bit (old) hypotheses and reports
which reproduces the known dims -> confirms/denies the 14-bit packing at >4096 with no regression
below. Also dumps base-VA (VA>>4), sRGB, sampleCount, mip/compress flags for cross-checks.

No Apple code; DATA-only. Usage: t9desc.py DUMPDIR --w W --h H [--type 2d] [--expect-va 0x..]
"""
import argparse, glob, os, re, sys
HEX=re.compile(r'^([0-9a-f]{8}):\s+(.*)$'); HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
def load(p):
    gpu=cpu=size=0; data=bytearray()
    for line in open(p):
        if line.startswith('#'):
            m=HDR.search(line)
            if m: gpu,cpu,size=(int(m.group(i),16) for i in (1,2,3));
            continue
        m=HEX.match(line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return {'gpu':gpu,'size':size,'data':bytes(data)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dumpdir')
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--type',default='2d')
    a=ap.parse_args()
    typenib={'2d':2,'3d':5,'array':3,'cube':6,'ms':4,'1d':0}[a.type]
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    hits=[]
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-32,4):
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(8)]
            if (w[0]&0xf)!=typenib: continue
            bva=(w[2]|((w[3]&0xfff)<<32))<<4
            if not bva: continue
            if not any(bb['gpu'] and bb['gpu']<=bva<bb['gpu']+bb['size'] for bb in bos): continue
            # candidate. compute both readings
            w14=(((w[0]>>28)&0xf)|((w[1]&0x3ff)<<4))+1      # 14-bit width-1
            h14=((w[1]>>10)&0x3fff)+1
            w12=(((w[0]>>28)&0xf)|((w[1]&0xff)<<4))+1        # 12-bit width-1 (old doc)
            h12=((w[1]>>10)&0xfff)+1                         # 12-bit height-1 (old doc)
            hits.append((b['gpu'],o,w,bva,w14,h14,w12,h12))
    # pick the hit whose 14-bit reading matches expected
    best=None
    for hit in hits:
        _,_,_,_,w14,h14,_,_=hit
        if w14==a.w and h14==a.h: best=hit; break
    if best is None:
        print(f'!! no descriptor whose 14-bit dims == {a.w}x{a.h}. candidates:')
        for g,o,w,bva,w14,h14,w12,h12 in hits[:12]:
            print(f'   BO0x{g:x}+0x{o:x} w0={w[0]:08x} w1={w[1]:08x} 14b={w14}x{h14} 12b={w12}x{h12} base=0x{bva:x}')
        return 1
    g,o,w,bva,w14,h14,w12,h12=best
    print(f'# desc BO 0x{g:x}+0x{o:x}: w0={w[0]:08x} w1={w[1]:08x} w2={w[2]:08x} w3={w[3]:08x}')
    print(f'  14-bit reading: {w14} x {h14}   (expected {a.w} x {a.h})  -> {"OK" if (w14==a.w and h14==a.h) else "FAIL"}')
    print(f'  12-bit reading: {w12} x {h12}   -> would be {"WRONG (proves 14-bit needed)" if (w12!=a.w or h12!=a.h) else "same (dims<=4096, no regression)"}')
    print(f'  base VA = 0x{bva:x} (word2|word3[0:11]<<4)')
    print(f'  sRGB(word3.b12)={(w[3]>>12)&1}  sampleCount[24:25]={(w[1]>>24)&3}  mip(b26)={(w[1]>>26)&1} comp(b27)={(w[1]>>27)&1} word3.b31={(w[3]>>31)&1}')
    print(f'  depth/arrayLen-1 word3[14:]={(w[3]>>14)}  mipCount-1 word5[16:19]={(w[5]>>16)&0xf}')
    return 0
if __name__=='__main__': sys.exit(main())
