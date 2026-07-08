#!/usr/bin/env python3
"""attloc.py -- locate & decode the 3D render-target attachment descriptor BO from an
iotrace dump, and correlate its pointer fields to known GPU VAs.

EXP-G1b (PBE / render-target descriptor). The attachment descriptor normally lands at
gpu_va 0x10000110000 (EXP-0014/0021) but can relocate when the RT format/size/MRT-count
changes the allocation. We therefore locate it by *content signature*: a chain of
0x300-byte segments, each beginning with a self-referential 8-byte pointer of the form
(BO_base + small_off) with the 0x0000_01xx_xxxx_xxxx tag, and carrying the packed
pixel-format word 0x??????02 (type=2D) / config 0x0000fc03 near +0x20.

Modes:
  attloc.py DUMPDIR [--va 0xADDR]        copy+decode the attachment BO (word view, first N)
  attloc.py DUMPDIR --curate OUT.hex     write the located attachment BO hex to OUT.hex
  attloc.py DUMPDIR --find 0xVA [0xVA..] search every BO for VA, VA>>4, VA>>8, VA (raw)

CLEAN-ROOM: DATA only (bytes from our own Metal process). No Apple code inspected.
"""
import argparse, glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu_va=cpu=size=0; data=bytearray(); rawhdr=''
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                rawhdr=line.rstrip('\n')
                m=HDR.search(line)
                if m: gpu_va,cpu,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'path':path,'gpu_va':gpu_va,'cpu':cpu,'size':size,'data':bytes(data),'hdr':rawhdr}

def w32(d,o): return int.from_bytes(d[o:o+4].ljust(4,b'\0'),'little') if o<len(d) else 0

def bos(dumpdir):
    out=[]
    for p in glob.glob(os.path.join(dumpdir,'*.hex')):
        out.append(load(p))
    return out

def is_attach(b):
    d=b['data']; base=b['gpu_va']
    if len(d)<0x30: return False
    p0=int.from_bytes(d[0:8],'little')
    # self-pointer into this BO within the first 0x40 bytes, tagged 0x000001xx........
    if not (base<=p0<base+0x40):
        # some captures begin with the store segment; also accept format word signature
        pass
    # packed format word: byte at +0x22/+0x322... == a plausible format; config word 0x0000fc03 pattern
    for segoff in (0x0,0x300,0x600):
        if segoff+0x28<=len(d):
            cfg=w32(d,segoff+0x24)
            if (cfg & 0xffff)==0xfc03 or (cfg & 0xffff0000)==0xfc000000 or cfg==0x0000fc03:
                return True
    # fallback: contains store-program id 0x6f near a store segment
    return b'\x6f\x00\x00\x00' in d[:0x1000] and (base & 0xfffff)==0x10000

def find_attach(dumpdir, va=None):
    cand=bos(dumpdir)
    if va is not None:
        for b in cand:
            if b['gpu_va']==va: return b
    # exact known VA first
    for b in cand:
        if b['gpu_va']==0x10000110000: return b
    # by signature
    hits=[b for b in cand if is_attach(b)]
    # prefer one in the 0x10000?????? resource range with size>=0x900
    hits.sort(key=lambda b:(-(b['size']>=0x900), b['gpu_va']))
    return hits[0] if hits else None

def decode(b, n=0x900):
    d=b['data']; base=b['gpu_va']
    print(f"# ATTACH BO gpu_va={base:#x} size={b['size']:#x}  ({os.path.basename(b['path'])})")
    for off in range(0, min(n,len(d)), 16):
        ws=' '.join(f'{w32(d,off+i):08x}' for i in range(0,16,4))
        # annotate segment starts
        tag=''
        if off%0x300==0: tag=f'  <-- seg{off//0x300}'
        print(f'  +{off:04x} (va {base+off:#011x}): {ws}{tag}')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--va', default=None)
    ap.add_argument('--curate', default=None)
    ap.add_argument('--find', nargs='+', default=None)
    ap.add_argument('--n', default='0x900')
    a=ap.parse_args()
    va=int(a.va,0) if a.va else None

    if a.find:
        needles=[int(x,0) for x in a.find]
        for b in bos(a.dumpdir):
            d=b['data']
            for va0 in needles:
                for shift,tagname in ((0,'raw'),(4,'>>4'),(8,'>>8')):
                    target=va0>>shift
                    tb=target.to_bytes(8,'little')
                    tb4=(target & 0xffffffff).to_bytes(4,'little')
                    i=d.find(tb4)
                    while i!=-1:
                        # confirm as 4-byte or 8-byte hit
                        print(f'  {va0:#x} {tagname} (={target:#x}) found in BO {b["gpu_va"]:#x} at +{i:#x}')
                        i=d.find(tb4,i+1)
        return 0

    b=find_attach(a.dumpdir, va)
    if not b:
        print(f'attachment BO not found in {a.dumpdir}'); return 1
    if a.curate:
        with open(a.curate,'w') as f:
            f.write(b['hdr']+'\n')
            d=b['data']
            for off in range(0,len(d),16):
                f.write(f'{off:08x}: '+' '.join(d[off+i:off+i+4].hex() for i in range(0,16,4))+' \n')
        print(f'curated {b["gpu_va"]:#x} -> {a.curate} ({len(b["data"]):#x} bytes)')
        return 0
    decode(b, int(a.n,0))
    return 0

if __name__=='__main__':
    sys.exit(main())
