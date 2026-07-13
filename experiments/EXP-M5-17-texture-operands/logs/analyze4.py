#!/usr/bin/env python3
import sys

def find_all_tex(b):
    offs=[]; i=0
    while i < len(b)-8:
        # tex op: byte0 low-nibble 0xf, byte+1 in {04,05,06,07}, byte+2 texture-class bit set
        if (b[i]&0x0f)==0x0f and b[i+1] in (0x04,0x05,0x06,0x07) and (b[i+2]&0x02)==0x02:
            offs.append(i); i+=8
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
    ops=[b[o:o+16] for o in offs]
    for o,op in zip(offs,ops):
        print(f"  @{o:3d}: {' '.join(f'{x:02x}' for x in op)}")
    if len(ops)==2:
        a,bb=ops; n=min(len(a),len(bb))
        diffs=[(k,a[k],bb[k]) for k in range(n) if a[k]!=bb[k]]
        print(f"  DIFF op0 vs op1: " + ", ".join(f"+{k}:{x:02x}->{y:02x}" for k,x,y in diffs))
