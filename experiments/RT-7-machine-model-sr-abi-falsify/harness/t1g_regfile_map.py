#!/usr/bin/env python3
# RT-7 Task 1b: full physical-GPR map + alias-vs-phantom, ALU path.
# 48 known live values a_k=in[k]=k+1, plus z=in[48]=0. Probe = a0 + z (plain
# register+register fadd, bit39=0 => byte+1 is genuinely srcA, per t1d). Trailing
# sum keeps a_k live at the probe. Splice probe.byte+1=(R<<1)|size -> out=content(R).
# Sweep R=0..127: reveals which physical regs hold known values, and whether
# r96..r127 return a known value (ALIAS) or 0 (phantom) or fault.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE)
from persistrun import PersistRunner
K=48
def src():
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device float* out [[buffer(0)]],",
       "              device const float* in [[buffer(1)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  float a%d = in[%d];"%(k,k))
    L.append("  float z = in[%d];"%K)
    L.append("  float probe = a0 + z;")
    L.append("  float s = z;")
    for k in range(K): L.append("  s += a%d;"%k)
    L.append("  out[gid*2+0] = probe;")
    L.append("  out[gid*2+1] = s;")
    L.append("}")
    return "\n".join(L)+"\n"
kp=os.path.join(HERE,"kernels","rfmap.metal"); open(kp,"w").write(src())
arch=os.path.join(HERE,"rfmap.bin")
subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
# find plain fadd with bit39==0 and srcB register (byte+3 != minifloat) -> first opsel-100, byte+4 bit7==0
i=0;n=len(main);cands=[]
while i+6<=n:
    if main[i]==0x09:
        length=8 if (main[i+2]&0x02) else 6
        if (main[i+2]&0x07)==0b100 and (main[i+4]>>7)==0:
            cands.append((i,length,main[i+1],main[i+3]))
        i+=length
    else: i+=2
print("plain-fadd candidates (off,len,byte1,byte3):",[(c[0],c[1],hex(c[2]),hex(c[3])) for c in cands[:8]],"...total",len(cands))
# probe = a0+z : pick the FIRST plain fadd (probe emitted before the sum chain? not guaranteed)
# Strategy: try each candidate, splice byte1 across a few R, pick the one where orig reads a known 'a' value.
inb=os.path.join(HERE,"rf_in.bin")
open(inb,"wb").write(b"".join(struct.pack("<f",k+1) for k in range(K))+struct.pack("<f",0.0))
r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
base=int(loc[0])
def sweep(off,b1):
    size=b1&1; abs1=base+off+1; res={}
    for R in range(0,128):
        spa=os.path.join(HERE,"rf_sp.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([(R<<1)|size]))
        resp=r.request(archive=spa,grid=1,tg=1,ins={1:inb},outs={0:8},timeout=8)
        v=struct.unpack_from('<f',resp["outs"][0],0)[0] if 0 in resp["outs"] and len(resp["outs"][0])>=4 else None
        res[R]=(resp["status"],v)
    return res
# use first candidate
off,length,b1,b3=cands[0]
print("using probe fadd off=%d byte1=0x%02x (srcA r%d) byte3=0x%02x"%(off,b1,b1>>1,b3))
res=sweep(off,b1)
r.close()
known={}; faults=[]; zeros=[]
for R in range(128):
    s,v=res[R]
    if s!="OK": faults.append(R)
    elif v is not None and abs(v-round(v))<1e-3 and 1<=round(v)<=K: known[R]=round(v)
    else: zeros.append(R)
print("\n=== physical reg map ===")
print("regs holding a known value (R -> a_(val-1)=in[val-1]):")
for R in sorted(known): print("  r%-3d = %d"%(R,known[R]))
print("num known-value regs:",len(known))
print("zero/other regs count:",len(zeros))
print("FAULT regs:",faults)
print("\n=== r90..r127 detail ===")
for R in range(90,128):
    s,v=res[R]; print("  r%-3d %-12s %s"%(R,s,v))
