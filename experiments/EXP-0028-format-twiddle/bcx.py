#!/usr/bin/env python3
"""bcx.py -- EXP-0028 part 3: solve the block-compressed BLOCK twiddle.

Reads iotrace dumps of a bcprobe run where compressed block (bx,by) has first
bytes [bx, by, 0x5a, 0xa5]. Locates the backing BO (densest in the 0xa55a tag),
maps block-slot index -> (bx,by), and solves it as a GF(2) function of the block
coords: linear (bx + by*BX) vs Morton-over-blocks (interleaved).

Usage: bcx.py DUMPDIR --bx BX --by BY --bb BLOCKBYTES [--label NAME]
"""
import argparse, glob, os, re, sys

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
    return {'gpu_va':gpu_va,'cpu':cpu,'size':size,'data':bytes(data)}

def u64(d,o): return int.from_bytes(d[o:o+8],'little') if o+8<=len(d) else 0

def find_base(bos, bo):
    for b in bos:
        d=b['data']
        if len(d)<0x14a8: continue
        p=u64(d,0x14a0)
        if b['gpu_va'] and b['gpu_va']<=p<b['gpu_va']+b['size']:
            o=p-b['gpu_va']
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(8)]
            base=(w[2]|((w[3]&0xfff)<<32))<<4
            if bo['gpu_va']<=base<bo['gpu_va']+bo['size']:
                return base,w
    return None,None

def count_tag(d):
    return sum(1 for o in range(0,len(d)-4,4) if d[o+2]==0x5a and d[o+3]==0xa5)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dumpdir'); ap.add_argument('--bx',type=int,required=True)
    ap.add_argument('--by',type=int,required=True); ap.add_argument('--bb',type=int,required=True)
    ap.add_argument('--label',default=None)
    a=ap.parse_args()
    BX,BY,BB=a.bx,a.by,a.bb; label=a.label or os.path.basename(a.dumpdir.rstrip('/'))
    bos=[load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir,'*.hex')))]
    if not bos: print(f'{label}: no dumps'); return 1
    ntag,bo=sorted(((count_tag(b['data']),b) for b in bos), key=lambda t:-t[0])[0]
    base,w=find_base(bos,bo)
    if base is None: base=bo['gpu_va']; w=None
    off0=base-bo['gpu_va']; d=bo['data']
    print(f"# {label}: BO 0x{bo['gpu_va']:x} sz=0x{bo['size']:x} base_off=0x{off0:x} tagged={ntag} expect={BX*BY}")
    if w: print(f"# desc: "+" ".join(f"{x:08x}" for x in w)+f"  byte0=0x{d[off0]:02x} byte1=0x{d[off0+1]:02x}")

    # map block-slot index (physical) -> (bx,by)
    slot2b={}
    nslots=(len(d)-off0)//BB
    for s in range(nslots):
        o=off0+s*BB
        if d[o+2]!=0x5a or d[o+3]!=0xa5: continue
        bx=d[o]; by=d[o+1]
        if bx>=BX or by>=BY: continue
        slot2b.setdefault((bx,by),s)
    print(f"# coverage {len(slot2b)}/{BX*BY}")
    if not slot2b: print(f"{label}: no block markers"); return 1

    # print physical slot grid
    print(f"## physical block-slot index for (bx,by):")
    print("      "+"".join(f"{x:5d}" for x in range(min(BX,12))))
    for y in range(min(BY,12)):
        print(f"by={y:2d} "+"".join((f"{slot2b[(x,y)]:5d}" if (x,y) in slot2b else "    .") for x in range(min(BX,12))))

    # GF(2) solve slot index as fn of bx-bits, by-bits
    kx=max(1,(BX-1).bit_length()); ky=max(1,(BY-1).bit_length())
    inputs=[('x',i) for i in range(kx)]+[('y',i) for i in range(ky)]
    S=list(slot2b.items())
    nb=max(s for _,s in S).bit_length()
    terms=[]; ok=True
    for b in range(nb):
        f=None
        for (nm,i) in inputs:
            if all(((s>>b)&1)==(((x if nm=='x' else y)>>i)&1) for (x,y),s in S): f=(nm,i); break
        if f is None:
            if all(((s>>b)&1)==0 for _,s in S): f=('0',0)
            else: f=('?',b); ok=False
        terms.append(f)
    expr=" | ".join(f"b{nm}{i}<<{b}" for b,(nm,i) in enumerate(terms) if nm in('x','y'))
    print(f"## GF(2) block_slot = {expr}")
    interl = any(nm=='y' for (nm,i) in terms[:kx]) or \
             [b for b,(nm,i) in enumerate(terms) if nm=='y' and b<kx]
    lin = all(terms[i][0]=='x' for i in range(kx)) and all(terms[kx+j][0]=='y' for j in range(ky) if kx+j<len(terms))
    print(f"## solved-cleanly={ok}; layout={'LINEAR (row-major blocks)' if lin else 'MORTON-over-blocks (interleaved)'}")
    return 0

if __name__=='__main__':
    sys.exit(main())
