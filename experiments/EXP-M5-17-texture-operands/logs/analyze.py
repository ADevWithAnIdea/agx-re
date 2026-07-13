#!/usr/bin/env python3
import sys

rows = {}
with open(sys.argv[1]) as f:
    for line in f:
        line=line.strip()
        if not line: continue
        name, hexs = line.split()
        rows[name] = bytes.fromhex(hexs)

def find_tex(b):
    # find first byte0 low-nibble 0xf with byte+2 in {0x12,0x16,0x1a} and byte+5==0x80
    for i in range(len(b)-6):
        if (b[i]&0x0f)==0x0f and b[i+2] in (0x12,0x16,0x1a) and b[i+5]==0x80:
            return i
    return None

for name,b in rows.items():
    off = find_tex(b)
    if off is None:
        print(f"{name:10s} NO-TEX  len={len(b)}")
        continue
    # print the tex op region up to next likely boundary (store 61.. or 27..)
    region = b[off:off+24]
    print(f"{name:10s} texoff={off:3d} totlen={len(b)}  op={region.hex()}")
