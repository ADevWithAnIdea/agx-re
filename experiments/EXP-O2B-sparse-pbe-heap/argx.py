#!/usr/bin/env python3
"""argx.py — auto-locate the Tier-2 argument buffer in an iotrace dump and extract the
appended texture + sampler descriptor blocks. Unlike EXP-0015's descx.py (fixed arg-BO VA),
this scans every captured BO for the one whose +0x14a0 word self-points (the texture-descriptor
pointer lands inside the same BO) — robust to the arg-BO VA shifting when the harness allocates
heaps. Binding order (EXP-0011): +0x14a0 texture ptr, +0x14a8 sampler ptr, +0x14b0 buffer(0).
CLEAN-ROOM: DATA only. Usage: argx.py DUMPDIR [--tlen 0x20] [--slen 0x10] [--words]"""
import argparse, glob, os, re, sys
HEX=re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(p):
    va=cpu=sz=0; d=bytearray()
    for line in open(p):
        if line.startswith('#'):
            m=HDR.search(line)
            if m: va,cpu,sz=(int(m.group(i),16) for i in (1,2,3))
            continue
        m=HEX.match(line)
        if not m: continue
        o=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(d)<o+len(b): d.extend(b'\x00'*(o+len(b)-len(d)))
        d[o:o+len(b)]=b
    return va,bytes(d)

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

def find_argbo(dumpdir):
    best=None
    for p in glob.glob(os.path.join(dumpdir,'*.hex')):
        if '/map_' in p or 'va0_' in p: continue
        va,d=load(p)
        if len(d)<0x14b8: continue
        t=u64(d,0x14a0)
        # texture-descriptor self-pointer: lands inside this same BO, above the table
        if va and va+0x14a0 <= t < va+len(d):
            best=(va,d,p); break
    return best

def hexblk(d,base_va,off,n,words):
    out=[]
    for r in range(0,n,16):
        line=d[off+r:off+r+16]
        if not line: break
        if words:
            ws=' '.join(f'{int.from_bytes(line[i:i+4].ljust(4,bytes(1)),"little"):08x}' for i in range(0,len(line),4))
            out.append(f'  +{r:04x} (va {base_va+r:#x}): {ws}')
        else:
            out.append(f'  +{r:04x}: '+line.hex())
    return '\n'.join(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--tlen',default='0x20'); ap.add_argument('--slen',default='0x10')
    ap.add_argument('--words',action='store_true')
    a=ap.parse_args(); tlen=int(a.tlen,0); slen=int(a.slen,0)
    r=find_argbo(a.dumpdir)
    if not r: print(f'# {a.dumpdir}: arg BO not found'); return 1
    argbo,d,p=r
    tptr=u64(d,0x14a0); sptr=u64(d,0x14a8); slot2=u64(d,0x14b0)
    print(f'# {a.dumpdir}  argBO={argbo:#x}')
    print(f'  slot0 @+0x14a0 = {tptr:#x}  (texture desc ptr)')
    print(f'  slot1 @+0x14a8 = {sptr:#x}  (sampler desc ptr)')
    print(f'  slot2 @+0x14b0 = {slot2:#x}  (buffer(0) VA)')
    def inbo(v): return argbo<=v<argbo+len(d)
    if inbo(tptr):
        print(f'TEXDESC @ {tptr:#x} (BO+{tptr-argbo:#x}):'); print(hexblk(d,tptr,tptr-argbo,tlen,a.words))
    if inbo(sptr):
        print(f'SAMPDESC @ {sptr:#x} (BO+{sptr-argbo:#x}):'); print(hexblk(d,sptr,sptr-argbo,slen,a.words))
    return 0
if __name__=='__main__': sys.exit(main())
