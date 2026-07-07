#!/usr/bin/env python3
# RT-1b item 4: falsify atomic_rmw op@byte+12, device/threadgroup byte+1 bit1,
# cmpxchg 0x24, and the threadgroup barrier (0x07 byte+3 mem-scope).
import rt1b

OPS = {0x20:"add",0x36:"sub",0x22:"and",0x2c:"or",0x3e:"xor",
       0x3c:"xchg",0x28:"smax",0x2a:"smin",0x38:"umax",0x3a:"umin"}

print("### rmw1 (single thread): out=op(c_init=12, in=10); op field @ byte+12")
h=rt1b.Harness("kernels/atom.metal","rmw1",workdir=".")
b=h.main
ao=[i for i in range(len(b)-13) if b[i]==0x67 and b[i+1]==0x11][0]
print("  atomic@+0x%x = %s  (op byte+12 = %#04x)"%(ao,b[ao:ao+14].hex(),b[ao+12]))
def cint(v): return rt1b.i32([v])
CIN={0:cint(12),1:cint(10)}
rb=h.run(grid=1,tg=1,ins=CIN,outs={2:8})
print("  baseline add: o0(old)=%d o1(new)=%d"%tuple(rt1b.di32(rb["outs"][2])))
import operator
ref={0x20:12+10,0x36:12-10,0x22:12&10,0x2c:12|10,0x3e:12^10,0x3c:10,
     0x28:max(12,10),0x2a:min(12,10),0x38:max(12,10),0x3a:min(12,10)}
print("  -- splice op byte+12:")
for op,name in OPS.items():
    r=h.run(splices=[(ao+12,bytes([op]))],ins=CIN,outs={2:8},grid=1,tg=1,timeout=10)
    if r["status"]!="OK": print("     %#04x %-5s -> %s"%(op,name,r["status"])); continue
    o0,o1=rt1b.di32(r["outs"][2])
    ok="OK" if o1==ref[op] else "MISMATCH(exp %d)"%ref[op]
    print("     %#04x %-5s -> new=%d  %s"%(op,name,o1,ok))

print("\n### cmpxchg (0x24): c=5, desired=99, expected=5 (match) then 7 (mismatch)")
h=rt1b.Harness("kernels/atom.metal","cxchg",workdir=".")
b=h.main; ao=[i for i in range(len(b)-13) if b[i]==0x67 and b[i+1]==0x01][0]
print("  cmpxchg@+0x%x = %s  (op byte+12 = %#04x)"%(ao,b[ao:ao+14].hex(),b[ao+12]))
for exp in [5,7]:
    r=h.run(grid=1,tg=1,ins={0:cint(5),1:rt1b.i32([99,exp])},outs={2:12})
    o=rt1b.di32(r["outs"][2]); print("  expected=%d -> swapped?=%d observed=%d cfinal=%d"%(exp,o[0],o[1],o[2]))

print("\n### device vs threadgroup: byte+1 bit1")
htg=rt1b.Harness("kernels/atom.metal","tgadd",workdir=".")
b=htg.main
tgat=[i for i in range(len(b)-13) if b[i]==0x67 and (b[i+1]&0x02)]
for i in tgat[:3]: print("  tg atomic @+0x%x byte+1=%#04x : %s"%(i,b[i+1],b[i:i+14].hex()))
# splice rmw1 device atomic byte+1 0x11 -> 0x13 (set bit1 = threadgroup) -> wrong space
h=rt1b.Harness("kernels/atom.metal","rmw1",workdir=".")
b=h.main; ao=[i for i in range(len(b)-13) if b[i]==0x67 and b[i+1]==0x11][0]
r=h.run(splices=[(ao+1,bytes([0x13]))],ins=CIN,outs={2:8},grid=1,tg=1,timeout=10)
print("  rmw1 byte+1 0x11->0x13 (device->tg space): status=%s out=%s (device counter should NOT update)"%(
      r["status"], rt1b.di32(r["outs"][2]) if r["status"]=="OK" else "-"))

print("\n### contended device atomic: agg 1024 threads add 1 -> 1024")
h=rt1b.Harness("kernels/atom.metal","agg",workdir=".")
b=h.main; ao=[i for i in range(len(b)-13) if b[i]==0x67 and b[i+1]==0x11][0]
r=h.run(grid=1024,tg=256,ins={0:cint(0)},outs={0:4})
print("  add: counter=%d (expect 1024)"%rt1b.di32(r["outs"][0])[0])
for op in [0x38,0x28,0x3c]:
    r=h.run(splices=[(ao+12,bytes([op]))],grid=1024,tg=256,ins={0:cint(0)},outs={0:4},timeout=10)
    print("  op->%#04x %-5s: counter=%s"%(op,OPS.get(op,"?"),rt1b.di32(r["outs"][0])[0] if r["status"]=="OK" else r["status"]))

print("\n### barrier: race kernel (grid=256), splice barrier byte+3 0x61->0x00 -> stale")
h=rt1b.Harness("kernels/atom.metal","race",workdir=".")
b=h.main; bo=[i for i in range(len(b)-5) if b[i]==0x07 and b[i+2]==0x54][0]
print("  barrier@+0x%x = %s (byte+3=%#04x)"%(bo,b[bo:bo+6].hex(),b[bo+3]))
A=rt1b.u32(list(range(256)))
rb=h.run(grid=256,tg=256,ins={0:A},outs={1:1024})
o=rt1b.du32(rb["outs"][1]); good=sum(1 for i in range(256) if o[i]==255-i)
print("  baseline: %d/256 lanes correct (out[gid]=255-gid)"%good)
rs=h.run(splices=[(bo+3,bytes([0x00]))],grid=256,tg=256,ins={0:A},outs={1:1024},timeout=12)
if rs["status"]=="OK":
    o=rt1b.du32(rs["outs"][1]); good=sum(1 for i in range(256) if o[i]==255-i); stale=sum(1 for v in o if v==0)
    print("  byte+3->0x00: status=OK %d/256 correct, %d lanes read 0 (stale) -> barrier scope load-bearing"%(good,stale))
else:
    print("  byte+3->0x00: status=%s"%rs["status"])
