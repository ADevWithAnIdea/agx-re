#!/usr/bin/env python3
"""descauto.py — auto-locate the Tier-2 argument buffer in an iotrace dump and
print the texture + sampler descriptor blocks it points to. Unlike descx.py this
does not hardcode the arg-BO VA (large textures shift it). It finds the BO whose
slot at +0x14a0 holds a u64 pointing back into itself (the texture-descriptor
pointer), then follows +0x14a0/+0x14a8. Clean-room: operates on captured DATA only.

Usage: descauto.py DUMPDIR [--tlen 0x20] [--slen 0x08]
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
    return {'gpu_va':gpu_va,'size':size,'data':bytes(data)}

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

def words(d,off,n):
    out=[]
    for r in range(0,n,16):
        line=d[off+r:off+r+16]
        if not line: break
        ws=' '.join(f'{int.from_bytes(line[i:i+4].ljust(4,bytes(1)),"little"):08x}' for i in range(0,len(line),4))
        out.append(f'  +{r:04x}: {ws}')
    return '\n'.join(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--tlen',default='0x20'); ap.add_argument('--slen',default='0x08')
    a=ap.parse_args(); tlen=int(a.tlen,0); slen=int(a.slen,0)
    bos=[load(p) for p in glob.glob(os.path.join(a.dumpdir,'*.hex'))]
    argbo=None; tptr=sptr=0
    for b in bos:
        if not b['gpu_va'] or len(b['data'])<0x14b0: continue
        t=u64(b['data'],0x14a0)
        if b['gpu_va']<=t<b['gpu_va']+b['size']:
            argbo=b; tptr=t; sptr=u64(b['data'],0x14a8); break
    if not argbo:
        print(f'arg BO not auto-found in {a.dumpdir}'); return 1
    d=argbo['data']; base=argbo['gpu_va']
    print(f'  ARGBO va={base:#x}  slot0(tex)={tptr:#x} slot1(samp)={sptr:#x}')
    def inbo(v): return base<=v<base+len(d)
    if inbo(tptr):
        print(f'TEXDESC @ {tptr:#x}:'); print(words(d,tptr-base,tlen))
    if inbo(sptr):
        print(f'SAMPDESC @ {sptr:#x}:'); print(words(d,sptr-base,slen))
    return 0
if __name__=='__main__': sys.exit(main())
