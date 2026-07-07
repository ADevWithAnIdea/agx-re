#!/usr/bin/env python3
# RT-7 Task 1b confirm: r96+ fault via an ALU (non-memory) path, and test whether
# a float ALU source can address r64..r95. Kernel out[gid]=x[gid]+y[gid] (both
# runtime loads => plain falu2, srcB is a register, bit39=0). srcA=byte+1 (=(reg<<1)|size).
# Splice byte+1 -> R and read out = content(R)+y. Uninit regs read 0 => out=y.
# If r96+ FAULTS (not 0) it is a register-decode fault, not memory OOB.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE)
from persistrun import PersistRunner

SRC="""#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device const float* x [[buffer(1)]],
              device const float* y [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = x[gid] + y[gid];
}
"""
def build():
    kp=os.path.join(HERE,"kernels","addxy.metal"); open(kp,"w").write(SRC)
    arch=os.path.join(HERE,"addxy.bin")
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    return kp,arch

if __name__=="__main__":
    kp,arch=build()
    buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    # find the fadd (0x09, opsel byte+2 low3 == 0b100), bit39 = byte+4 bit7
    i=0; n=len(main); fadd=None
    while i+6<=n:
        if main[i]==0x09:
            length=8 if (main[i+2]&0x02) else 6
            if (main[i+2]&0x07)==0b100:
                fadd=(i,length,main[i:i+length].hex(),main[i+4] if i+4<n else 0)
                break
            i+=length
        else: i+=2
    print("fadd",fadd)
    off,length,hx,b4=fadd
    print("bytes=%s  byte+1=0x%02x srcA r%d  byte+4=0x%02x bit39=%d"%(hx,main[off+1],main[off+1]>>1,b4,(b4>>7)&1))
    size=main[off+1]&1
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
    splice_abs=int(loc[0])+off+1
    xb=os.path.join(HERE,"ax.bin"); yb=os.path.join(HERE,"ay.bin")
    open(xb,"wb").write(struct.pack("<f",7.0)); open(yb,"wb").write(struct.pack("<f",100.0))
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    print("orig: out should be 7+100=107 at R=srcA")
    for R in list(range(58,72))+list(range(90,104))+[110,120,127]:
        spa=os.path.join(HERE,"ax_sp.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f: f.seek(splice_abs); f.write(bytes([(R<<1)|size]))
        resp=r.request(archive=spa,grid=1,tg=1,ins={1:xb,2:yb},outs={0:4},timeout=8)
        v=struct.unpack_from('<f',resp["outs"][0],0)[0] if 0 in resp["outs"] and len(resp["outs"][0])>=4 else None
        note=""
        if resp["status"]=="OK" and v is not None:
            if abs(v-100.0)<1e-3: note="=0+y (uninit reg -> 0)"
            elif abs(v-107.0)<1e-3: note="=x+y (orig srcA reg)"
            else: note="content=%.5f (minifloat? %s)"%(v-100.0,"yes" if 0<v-100<31 else "")
        print("R=%-3d %-12s out=%s %s"%(R,resp["status"],v,note))
        sys.stdout.flush()
    r.close()
