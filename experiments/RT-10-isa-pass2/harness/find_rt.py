#!/usr/bin/env python3
# Find rt_intersect (byte0 low-nibble 0x4, byte+1==0xea, 8B) and rt loads (0xdf/0x5f)
# in the extracted p4 kernels, and byte-diff the two _agc.main streams.
import sys
def load(path):
    h={}
    for line in open(path):
        p=line.split()
        if len(p)==2: h[p[0]]=p[1]
    return h
h=load(sys.argv[1])
def find_rt(name, hx):
    b=bytes.fromhex(hx)
    print(f"\n===== {name} ({len(b)}B) rt_intersect (X4 ea) + rt_as_load (df) + ray_data (5f) =====")
    i=0
    while i < len(b)-1:
        if (b[i]&0x0f)==0x04 and b[i+1]==0xea:
            print(f"  +0x{i:03x} rt_intersect  {b[i:i+8].hex()}")
            i+=8; continue
        if b[i]==0xdf:
            print(f"  +0x{i:03x} rt_as_load    {b[i:i+14].hex()}")
            i+=14; continue
        if b[i]==0x5f:
            print(f"  +0x{i:03x} ray_data(5f)  {b[i:i+14].hex()}")
            i+=14; continue
        i+=1
for k in sorted(h):
    if k.startswith("p4"):
        find_rt(k, h[k])
