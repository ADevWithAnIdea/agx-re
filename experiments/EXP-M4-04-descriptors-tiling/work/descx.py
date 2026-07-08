#!/usr/bin/env python3
"""descx.py -- extract the appended texture/sampler descriptor blocks from an
iotrace capture of the Tier-2 argument buffer (BO gpu_va 0x100000e0000).

EXP-0015 (Phase 3, descriptors). The argument buffer holds, at +0x14a0, a table
of 8-byte slots in binding order (EXP-0011):
  slot0 [[texture(0)]] = pointer to a texture descriptor appended in the same BO
  slot1 [[sampler(0)]] = pointer to a sampler descriptor appended in the same BO
  slot2 [[buffer(0)]]  = inline GPU VA (a data buffer, not a pointer into this BO)
When the kernel has no sampler (multisample read path) slot1 is the buffer VA.

descx follows those pointers (which land inside this same BO) and dumps N bytes at
each target, so descriptors can be diffed regardless of where in the BO they land.

CLEAN-ROOM: DATA only (bytes captured from our own Metal process). No Apple code.

Usage:
  descx.py DUMPDIR [--argbo 0x100000e0000] [--tlen 0x30] [--slen 0x30] [--words]
"""
import argparse, glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

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
    return {'path':path,'gpu_va':gpu_va,'data':bytes(data)}

def find_bo(dumpdir, va):
    for p in glob.glob(os.path.join(dumpdir,'*.hex')):
        b=load(p)
        if b['gpu_va']==va: return b
    return None

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

def hexblk(d, base_va, off, n, words):
    out=[]
    for r in range(0,n,16):
        line=d[off+r:off+r+16]
        if not line: break
        if words:
            ws=' '.join(f'{int.from_bytes(line[i:i+4].ljust(4,bytes(1)),"little"):08x}'
                        for i in range(0,len(line),4))
            out.append(f'  +{r:04x} (va {base_va+r:#x}): {ws}')
        else:
            out.append(f'  +{r:04x}: '+line.hex())
    return '\n'.join(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--argbo', default='0x100000e0000')
    ap.add_argument('--tlen', default='0x30')
    ap.add_argument('--slen', default='0x30')
    ap.add_argument('--words', action='store_true')
    a=ap.parse_args()
    argbo=int(a.argbo,0); tlen=int(a.tlen,0); slen=int(a.slen,0)
    bo=find_bo(a.dumpdir, argbo)
    if not bo:
        print(f'arg BO {argbo:#x} not found in {a.dumpdir}'); return 1
    d=bo['data']
    tptr=u64(d,0x14a0); sptr=u64(d,0x14a8); slot2=u64(d,0x14b0)
    print(f'# {a.dumpdir}')
    print(f'  slot0 @+0x14a0 = {tptr:#x}  (texture desc ptr)')
    print(f'  slot1 @+0x14a8 = {sptr:#x}  (sampler desc ptr, or buffer VA if no sampler)')
    print(f'  slot2 @+0x14b0 = {slot2:#x}')
    def inbo(v): return argbo<=v<argbo+0x100000
    if inbo(tptr):
        toff=tptr-argbo
        print(f'TEXDESC @ va {tptr:#x} (BO+{toff:#x}):')
        print(hexblk(d,tptr,toff,tlen,a.words))
    if inbo(sptr):
        soff=sptr-argbo
        print(f'SAMPDESC @ va {sptr:#x} (BO+{soff:#x}):')
        print(hexblk(d,sptr,soff,slen,a.words))
    return 0

if __name__=='__main__':
    sys.exit(main())
