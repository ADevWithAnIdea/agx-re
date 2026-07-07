#!/usr/bin/env python3
"""pbecheck.py -- RT-3 PBE (storage-image) descriptor falsifier.

Follows the arg-buffer slot0 pointer to the descriptor region and decodes the PBE
width/height packing (DIFFERENT split than the sampled descriptor):
  width-1  = word0[24:31] || word1[0:5]   (8+6 = 14 bits)
  height-1 = word1[6:19]                   (14 bits)
  base VA  = word2 || word3[0:11] << 4
Checks W/H against config, and for --access readwrite verifies TWO 32-byte
descriptors are appended (a read texture desc + a PBE desc).

CLEAN-ROOM: DATA only.
Usage: pbecheck.py DUMPDIR --obuf 0xVA --w W --h H [--access write|readwrite]
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
def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0
def w32(d,o): return int.from_bytes(d[o:o+4].ljust(4,b'\0'),'little')
def dec_pbe(w):
    width=(((w[0]>>24)&0xff)|((w[1]&0x3f)<<8))+1
    height=((w[1]>>6)&0x3fff)+1
    bva=(w[2]|((w[3]&0xfff)<<32))<<4
    return width,height,bva
def dec_sampled(w):
    width=(((w[0]>>28)&0xf)|((w[1]&0x3ff)<<4))+1
    height=((w[1]>>10)&0x3fff)+1
    return width,height
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dumpdir'); ap.add_argument('--obuf',required=True)
    ap.add_argument('--w',type=int,required=True); ap.add_argument('--h',type=int,required=True)
    ap.add_argument('--access',default='write')
    a=ap.parse_args(); obuf=int(a.obuf,0); ob=obuf.to_bytes(8,'little')
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    B=None
    for b in bos:
        d=b['data']
        if len(d)>=0x14c8 and ob in d[0x1490:0x14c8]: B=b; break
    if not B: print('!! arg BO not found'); return 1
    d=B['data']; base=B['gpu_va']
    slots=[u64(d,0x14a0+8*k) for k in range(4)]
    print('# slots: '+' '.join(f's{k}=0x{v:x}{"(ptr+0x%x)"%(v-base) if base<=v<base+B["size"] else ""}' for k,v in enumerate(slots)))
    # descriptor region typically at +0x14c0; dump up to 2 descriptors (0x40)
    start=0x14c0
    descs=[]
    for k in range(2):
        o=start+0x20*k
        w=[w32(d,o+4*i) for i in range(8)]
        if all(x==0 for x in w): break
        descs.append((o,w))
    print(f'# {len(descs)} appended 32B descriptor(s) at +0x{start:x}')
    np=[0,0]
    def chk(n,g,e):
        ok=g==e; np[0]+=1; np[1]+=ok; print(f'  {"PASS" if ok else "FAIL"} {n}: got={g} exp={e}')
    for i,(o,w) in enumerate(descs):
        print(f'  desc{i} @+0x{o:x}: '+' '.join(f'{x:08x}' for x in w))
        pw,ph,bva=dec_pbe(w); sw,sh=dec_sampled(w)
        print(f'    PBE-split W={pw} H={ph} baseVA=0x{bva:x} | sampled-split W={sw} H={sh} | comp(w1.b27)={(w[1]>>27)&1} w3.b31={(w[3]>>31)&1} w4={w[4]:08x}')
    if a.access=='readwrite':
        chk('read_write -> TWO descriptors',len(descs),2)
        if len(descs)==2:
            # last one is the PBE (write) descriptor
            pw,ph,_=dec_pbe(descs[-1][1]); chk('PBE width',pw,a.w); chk('PBE height',ph,a.h)
            # first is compression-disabled read texture desc
            comp0=(descs[0][1][1]>>27)&1; chk('read-desc comp disabled (w1.b27==0)',comp0,0)
    else:
        chk('write -> ONE descriptor',len(descs),1)
        pw,ph,_=dec_pbe(descs[0][1]); chk('PBE width (word0[24:31]||word1[0:5])',pw,a.w); chk('PBE height (word1[6:19])',ph,a.h)
    print(f'# SUMMARY {np[1]}/{np[0]} PASS')
    return 0
if __name__=='__main__': sys.exit(main())
