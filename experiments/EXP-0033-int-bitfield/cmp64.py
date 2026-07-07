import os, struct, importlib.util
HERE="."
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
ip=lm("intprobe","intprobe.py")
def u64(v): return b"".join(struct.pack("<Q",x&(2**64-1)) for x in v)
def i64(v): return b"".join(struct.pack("<q",x) for x in v)
A=[0x1_0000_0000, 0x5, 0xFFFF_FFFF_FFFF_FFFF, 0x2_0000_0000]
B=[0x0_FFFF_FFFF, 0x5, 0x1,                    0x3_0000_0000]
p=ip.IntProbe("kernels/u64_cmp.metal")
r=p.run({},{0:u64(A),1:u64(B)},{2:len(A)},grid=len(A),signed=False);p.close()
print("u64_cmp(a<b) got",[x&0xffffffff for x in r[2]],"exp",[1 if a<b else 0 for a,b in zip(A,B)])
SA=[-1, 5, -0x1_0000_0000, 3]
SB=[ 1, 5, -1,             -3]
p=ip.IntProbe("kernels/s64_cmp.metal")
r=p.run({},{0:i64(SA),1:i64(SB)},{2:len(SA)},grid=len(SA),signed=True);p.close()
print("s64_cmp(a<b) got",r[2],"exp",[1 if a<b else 0 for a,b in zip(SA,SB)])
