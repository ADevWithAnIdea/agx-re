#!/usr/bin/env python3
# RT-1b: vector loads (byte+5 is index reg, NOT count; width lives at byte+8/+12)
# and threadgroup-space (byte+1=0x02) cross-check.
import rt1b
def ld(h):
    return [(t["off"],t["hex"]) for t in h.tokens() if t["byte0"]==0x67]
def st(h):
    return [(t["off"],t["hex"]) for t in h.tokens() if t["byte0"]==0xe7]

print("## load byte layout: scalar vs uint2 vs uint4 (width should be byte+8/+12, not byte+5)")
for fn in ["dev","v2","v4"]:
    h=rt1b.Harness("kernels/mem.metal",fn,workdir=".")
    for off,hx in ld(h):
        b=bytes.fromhex(hx)
        print("  %-4s load: %s   byte+5=%#04x byte+8=%#04x byte+12=%#04x"%(fn,hx,b[5],b[8],b[12]))

print("\n## v4 semantics: one load moves 4 words")
h=rt1b.Harness("kernels/mem.metal","v4",workdir=".")
import struct
A=rt1b.u32(list(range(1,9)))     # 2 uint4 elements
r=h.run(grid=2,tg=2,ins={1:A},outs={0:32})
print("  out:",rt1b.du32(r["outs"][0]),"(expect 1..8)")
print("  #0x67 loads in v4 main:",len(ld(h)),"#0xe7 stores:",len(st(h)))

print("\n## threadgroup space: tg kernel load/store byte+1 should be 0x02 (device is 0x00)")
h=rt1b.Harness("kernels/mem.metal","tg",workdir=".")
for off,hx in ld(h):
    print("  tg load @+0x%x: %s  byte+1=%#04x"%(off,hx,bytes.fromhex(hx)[1]))
for off,hx in st(h):
    print("  tg store@+0x%x: %s  byte+1=%#04x"%(off,hx,bytes.fromhex(hx)[1]))
# semantics: tile[lid]=a[gid]; barrier; out[gid]=tile[lid]
A=rt1b.i32([10,20,30,40,50,60,70,80])
r=h.run(grid=8,tg=8,ins={1:A},outs={0:32})
print("  tg copy out:",rt1b.di32(r["outs"][0]),"(expect 10..80)")
