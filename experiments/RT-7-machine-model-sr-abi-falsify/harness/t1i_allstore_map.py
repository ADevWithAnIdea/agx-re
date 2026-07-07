#!/usr/bin/env python3
# RT-7 Task 1b: physical-GPR map + alias/phantom. EXACT EXP-0020 cyclic all-store
# kernel (stores every a_k => all K live) PLUS a trailing probe fadd out[K]=a0+z.
# n=1 => a_k=in[k]=k+1. Splice probe.byte+1 (srcA, plain fadd bit39=0) to read
# physical reg R. r96..r127 returning a KNOWN value => alias; 0 => phantom; fault.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE)
from persistrun import PersistRunner
K=int(os.environ.get("K","60"))
def src():
    W=K+2
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device float* out [[buffer(0)]],",
       "              device const float* in [[buffer(1)]],",
       "              constant uint& n [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  float a%d = in[%d];"%(k,k))
    L.append("  float z = in[%d];"%K)
    L.append("  for (uint i=1;i<n;i++){ float t=in[i];")
    for k in range(K): L.append("    a%d = a%d*t + a%d;"%(k,k,(k+1)%K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d] = a%d;"%(W,k,k))
    L.append("  float probe = a0 + z;")
    L.append("  out[gid*%d+%d] = probe;"%(W,K))
    L.append("}")
    return "\n".join(L)+"\n", W
s,W=src()
kp=os.path.join(HERE,"kernels","allst.metal"); open(kp,"w").write(s)
arch=os.path.join(HERE,"allst.bin")
subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
print("MAIN_LEN",len(main),"W",W)
# probe = LAST plain fadd (bit39==0)
i=0;n=len(main);cands=[]
while i+2<=n:
    b0=main[i]
    if b0==0x09:
        length=8 if (main[i+2]&0x02) else 6
        if (main[i+2]&0x07)==0b100 and (main[i+4]>>7)==0: cands.append((i,main[i+1],main[i+3]))
        i+=length
    elif b0 in (0x67,0xe7): i+=14
    elif b0==0x0e: i+=4
    elif (b0&0x0f)==0x0c: i+=4
    else: i+=2
print("plain-fadd count:",len(cands),"last few:",[(c[0],hex(c[1])) for c in cands[-4:]])
if not cands: sys.exit("no plain fadd")
off,b1,b3=cands[-1]
print("probe off=%d byte1=0x%02x srcA r%d"%(off,b1,b1>>1))
inb=os.path.join(HERE,"as_in.bin"); nb=os.path.join(HERE,"as_n.bin")
open(inb,"wb").write(b"".join(struct.pack("<f",k+1) for k in range(K))+struct.pack("<f",0.0))
open(nb,"wb").write(struct.pack("<I",1))
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
base=int(loc[0]); abs1=base+off+1; size=b1&1
r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
# baseline (no splice) to confirm probe reads a0=in[0]=1
resp0=r.request(archive=arch,grid=1,tg=1,ins={1:inb,2:nb},outs={0:W*4},timeout=8)
base_probe=struct.unpack_from('<f',resp0["outs"][0],K*4)[0] if 0 in resp0["outs"] else None
print("baseline probe out[K] =",base_probe,"(expect a0+z=1.0)  status",resp0["status"])
res={}
for R in range(0,128):
    spa=os.path.join(HERE,"as_sp.bin"); shutil.copyfile(arch,spa)
    with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([(R<<1)|size]))
    resp=r.request(archive=spa,grid=1,tg=1,ins={1:inb,2:nb},outs={0:W*4},timeout=8)
    v=struct.unpack_from('<f',resp["outs"][0],K*4)[0] if 0 in resp["outs"] and len(resp["outs"][0])>=W*4 else None
    res[R]=(resp["status"],v)
r.close()
known={};faults=[];zeros=[]
for R in range(128):
    s,v=res[R]
    if s!="OK": faults.append(R)
    elif v is not None and abs(v-round(v))<1e-2 and 1<=round(v)<=K: known[R]=round(v)
    else: zeros.append(R)
print("\nknown-value physical regs:")
for R in sorted(known): print("  r%-3d = in[%d] (=%d)"%(R,known[R]-1,known[R]))
print("count known:",len(known)," distinct:",len(set(known.values())),"/",K," zeros:",len(zeros)," faults:",len(faults))
print("\nr90..r127:")
for R in range(90,128):
    s,v=res[R]; tag="KNOWN in[%d]"%(known[R]-1) if R in known else ("FAULT" if s!="OK" else "zero")
    print("  r%-3d %-12s %-10s %s"%(R,s,v,tag))
