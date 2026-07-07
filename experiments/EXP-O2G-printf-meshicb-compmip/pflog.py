#!/usr/bin/env python3
"""pflog.py -- locate and structurally decode the shader printf / os_log records in an
iotrace BO dump (EXP-O2G part 1).

The printf kernel emits distinctive marker constants (0x51abcdef and 0xdd00+i, thread ids
0..3, float 0.25=0x3e800000). We scan every captured BO for those needles to (a) identify
which BO is the shader-logging buffer, and (b) dump a hex window around each record so the
record framing (header word(s) = format-string id + size + thread coords, then the packed
argument payload) can be read off. All bytes are DATA our own process produced.

Usage: pflog.py DUMPDIR
"""
import glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu_va=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu_va,_,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'path':os.path.basename(path),'gpu_va':gpu_va,'size':size,'data':bytes(data)}

def le32(v): return v.to_bytes(4,'little')

def hexwin(d, center, before=16, after=64):
    lo=max(0,(center-before)&~0xf); hi=min(len(d),center+after)
    out=[]
    for r in range(lo,hi,16):
        row=d[r:r+16]
        out.append(f'    +{r:04x}: '+' '.join(f'{x:02x}' for x in row))
    return '\n'.join(out)

def main():
    dumpdir=sys.argv[1]
    bos=[load(p) for p in glob.glob(os.path.join(dumpdir,'*.hex'))]
    bos=[b for b in bos if b['gpu_va']]
    by_va={b['gpu_va']:b for b in bos}
    print(f'# {dumpdir}: {len(bos)} BOs')

    needles={
        'MARK 0x51abcdef': le32(0x51abcdef),
        'g=0xdd00':        le32(0xdd00),
        'g=0xdd02':        le32(0xdd02),
        'float 0.25':      le32(0x3e800000),
        'float 2.25':      le32(0x40100000),
    }
    # score BOs by how many marker hits they contain (the log buffer wins)
    scores={}
    for b in bos:
        s=b['data'].count(le32(0x51abcdef))
        if s: scores[b['gpu_va']]=s
    if scores:
        print('\n# BOs containing 0x51abcdef marker (hit count):')
        for va,c in sorted(scores.items(),key=lambda x:-x[1]):
            bb=by_va[va]
            print(f'  {va:#x} size={bb["size"]:#x} hits={c} ({bb["path"]})')

    for name,nd in needles.items():
        print(f'\n# needle {name} ({nd.hex()}):')
        n=0
        for b in bos:
            d=b['data']; start=0
            while True:
                i=d.find(nd,start)
                if i<0: break
                n+=1
                print(f'  hit in BO {b["gpu_va"]:#x} (size {b["size"]:#x}) @ +{i:#x}')
                print(hexwin(d,i))
                start=i+1
                if n>24: break
            if n>24: break
        if n==0: print('  (none)')
    return 0

if __name__=='__main__':
    if len(sys.argv)<2: print('usage: pflog.py DUMPDIR'); sys.exit(2)
    sys.exit(main() or 0)
