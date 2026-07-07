#!/usr/bin/env python3
# RT-1b item 3: falsify CALL (0f05, target=call+4+off40) / RETURN (8f) /
# calling convention / nested / recursion->loop / many-arg spill.
import rt1b, struct

def off40(b, o):     # decode signed 40-bit LE at b[o:o+5]
    v = int.from_bytes(b[o:o+5], "little")
    if v & (1<<39): v -= (1<<40)
    return v

print("### CALL target formula: two call sites -> same target (target=call+4+off40)")
h=rt1b.Harness("kernels/call.metal","twocall",workdir=".")
b=h.main
calls=[i for i in range(len(b)-6) if b[i]==0x0f and b[i+1]==0x05 and b[i+4]==0x8f and b[i+6]==0x56]
for c in calls:
    o=off40(b,c+7)
    print("  call@+0x%02x off40=%d  target(call+4+off40)=%+d"%(c,o,c+4+o))
if len(calls)==2:
    t0=calls[0]+4+off40(b,calls[0]+7); t1=calls[1]+4+off40(b,calls[1]+7)
    print("  => both targets equal? %s (t0=%d t1=%d)"%(t0==t1,t0,t1))
# semantics: hadd(hadd(A,B),B) = A+2B
A=rt1b.f32([3,5,7,9]); B=rt1b.f32([1,2,3,4])
r=h.run(grid=4,tg=4,ins={0:A,1:B},outs={2:16})
print("  twocall out:",rt1b.df32(r["outs"][2]),"expect A+2B=",[3+2,5+4,7+6,9+8])

print("\n### off40 is load-bearing: corrupt the target -> fault/wrong")
h1=rt1b.Harness("kernels/call.metal","one",workdir=".")
b=h1.main
c=[i for i in range(len(b)-6) if b[i]==0x0f and b[i+1]==0x05 and b[i+4]==0x8f and b[i+6]==0x56][0]
A=rt1b.f32([2,3,4,5]); B=rt1b.f32([10,10,10,10])
rb=h1.run(grid=4,tg=4,ins={0:A,1:B},outs={2:16})
print("  baseline helper2=A*B+1:",rt1b.df32(rb["outs"][2]),"expect",[2*10+1,3*10+1,4*10+1,5*10+1])
for delta in [0x02, 0x10]:
    nb=(b[c+7]+delta)&0xff
    r=h1.run(splices=[(c+7,bytes([nb]))],grid=4,tg=4,ins={0:A,1:B},outs={2:16},timeout=10)
    print("  off40 byte+7 %#04x->%#04x : status=%s out=%s"%(b[c+7],nb,r["status"],
          rt1b.df32(r["outs"][2]) if r["status"]=="OK" else "-"))
    rc=h1.run(grid=4,tg=4,ins={0:A,1:B},outs={2:16})  # recovery
    print("    recovery:",rc["status"])

print("\n### nested (3-level): chain O=mid(A)=8A+2")
h=rt1b.Harness("kernels/call.metal","chain",workdir=".")
A=rt1b.f32([1,2,3,4])
r=h.run(grid=4,tg=4,ins={0:A},outs={1:16})
print("  chain out:",rt1b.df32(r["outs"][1]),"expect",[8*x+2 for x in [1,2,3,4]])

print("\n### recursion->loop: recur O=A*1.1^N")
h=rt1b.Harness("kernels/call.metal","recur",workdir=".")
A=rt1b.f32([2,2,2,2]); N=rt1b.i32([0,1,5,10])
r=h.run(grid=4,tg=4,ins={0:A,1:N},outs={2:16})
print("  recur out:",[round(v,4) for v in rt1b.df32(r["outs"][2])],"expect",[round(2*1.1**n,4) for n in [0,1,5,10]])

print("\n### many-arg spill: spill O=sum(A[0..11])")
h=rt1b.Harness("kernels/call.metal","spill",workdir=".")
A=rt1b.f32(list(range(1,13)))
r=h.run(grid=1,tg=1,ins={0:A},outs={1:4})
print("  spill out:",rt1b.df32(r["outs"][1]),"expect",sum(range(1,13)))
# confirm frame marker present
print("  frame markers 43 00 00 01 in main:",
      [hex(i) for i in range(len(h.main)-3) if h.main[i:i+4]==bytes.fromhex("43000001")])
