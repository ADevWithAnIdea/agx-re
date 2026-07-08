#!/usr/bin/env python3
"""argx2.py -- locate the Tier-2 compute argument buffer in an iotrace dump (by the
inline output-buffer VA that lands in the +0x14a0 slot table) and dump the slot table
plus the appended descriptor block, regardless of which BO/VA the arg buffer relocated to.

EXP-G1b objective-1 (storage-image / PBE descriptor). Metal's auto argument buffer holds
an 8-byte slot per bound resource at +0x14a0 (EXP-0011); textures/samplers store a pointer
to a descriptor appended in the same BO (typically at +0x14c0), buffers store an inline VA.
Binding a texture as access::write vs access::sample changes the appended descriptor; this
tool dumps it so the two can be byte-diffed.

Usage:
  argx2.py DUMPDIR --obuf 0xVA [--n 0x60] [--words]
  argx2.py DUMPDIR --obuf 0xVA --curate OUT.hex   # write the descriptor region to a file

CLEAN-ROOM: DATA only. No Apple code inspected.
"""
import argparse, glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu_va=cpu=size=0; data=bytearray(); hdr=''
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                hdr=line.rstrip('\n'); m=HDR.search(line)
                if m: gpu_va,cpu,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'path':path,'gpu_va':gpu_va,'size':size,'data':bytes(data),'hdr':hdr}

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0
def w32(d,o): return int.from_bytes(d[o:o+4].ljust(4,b'\0'),'little')

def find_argbo(dumpdir, obuf):
    ob=obuf.to_bytes(8,'little')
    for p in glob.glob(os.path.join(dumpdir,'*.hex')):
        b=load(p); d=b['data']
        # search the table window +0x14a0..+0x14c0 for the inline obuf VA
        win=d[0x1490:0x14c8]
        if ob in win:
            return b
    # fallback: any BO containing obuf VA at an 8-aligned slot below 0x1500
    for p in glob.glob(os.path.join(dumpdir,'*.hex')):
        b=load(p); d=b['data']
        i=d.find(ob)
        if 0x1400<=i<0x1500: return b
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--obuf',required=True)
    ap.add_argument('--n',default='0x60'); ap.add_argument('--words',action='store_true')
    ap.add_argument('--curate',default=None)
    a=ap.parse_args(); obuf=int(a.obuf,0); n=int(a.n,0)
    b=find_argbo(a.dumpdir,obuf)
    if not b: print(f'arg BO (obuf {obuf:#x}) not found in {a.dumpdir}'); return 1
    d=b['data']; base=b['gpu_va']
    print(f'# ARG BO gpu_va={base:#x}  ({os.path.basename(b["path"])})  obuf={obuf:#x}')
    for k in range(4):
        v=u64(d,0x14a0+8*k)
        kind='ptr->BO+%#x'%(v-base) if base<=v<base+0x100000 else ('obuf' if v==obuf else 'inline/other')
        print(f'  slot{k} @+{0x14a0+8*k:#x} = {v:#018x}  {kind}')
    # descriptor region starts right after the table, at +0x14c0
    start=0x14c0
    if a.curate:
        with open(a.curate,'w') as f:
            f.write(b['hdr']+'\n')
            for off in range(start,start+n,16):
                f.write(f'{off:08x}: '+' '.join(d[off+i:off+i+4].hex() for i in range(0,16,4))+' \n')
        print(f'curated {base:#x} desc region +{start:#x}..+{start+n:#x} -> {a.curate}')
        return 0
    print(f'DESC region @ +{start:#x} (va {base+start:#x}):')
    for off in range(start,start+n,16):
        if a.words:
            ws=' '.join(f'{w32(d,off+i):08x}' for i in range(0,16,4))
            print(f'  +{off-start:04x} (va {base+off:#x}): {ws}')
        else:
            print(f'  +{off-start:04x}: '+' '.join(d[off+i:off+i+4].hex() for i in range(0,16,4)))
    return 0

if __name__=='__main__':
    sys.exit(main())
