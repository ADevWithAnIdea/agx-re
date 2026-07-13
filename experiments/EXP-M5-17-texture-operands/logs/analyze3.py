#!/usr/bin/env python3
import sys

def find_all_tex(b):
    offs=[]
    i=0
    while i < len(b)-6:
        # texture-class: byte0 low-nibble 0xf, byte+2 in {12,16,1a}, byte+4 hi-nibble 0x4
        if (b[i]&0x0f)==0x0f and b[i+2] in (0x12,0x16,0x1a) and (b[i+4]&0xf0)==0x40:
            offs.append(i); i+=6
        else:
            i+=1
    return offs

rows={}
with open(sys.argv[1]) as f:
    for line in f:
        line=line.strip()
        if not line: continue
        name,hexs=line.split()
        rows[name]=bytes.fromhex(hexs)

for name,b in rows.items():
    offs=find_all_tex(b)
    print(f"\n=== {name}  len={len(b)}  tex_offs={offs} ===")
    ops=[b[o:o+22] for o in offs]
    for o,op in zip(offs,ops):
        sp=' '.join(f'{x:02x}' for x in op)
        print(f"  @{o:3d}: {sp}")
    if len(ops)==2:
        a,bb=ops
        n=min(len(a),len(bb))
        diffs=[(k,a[k],bb[k]) for k in range(n) if a[k]!=bb[k]]
        print(f"  DIFF op0 vs op1: " + ", ".join(f"+{k}:{x:02x}->{y:02x}" for k,x,y in diffs))
