#!/usr/bin/env python3
# RT-7 Task 1b DECISIVE alias test (ALU path). Kernel: t=x[gid]; out=t+y[gid].
# Splice the LOAD dst (byte+8, reg=byte8>>1) to force x into a chosen physical
# reg WR; splice the fadd srcA (byte+1, reg=byte1>>1) to read from RR.
#   x=7, y=100.  out=107 <=> WR and RR are the SAME physical register.
# Test: WR=0 (x->r0), RR in {0(ctrl),95(ctrl),96,97,100,127,32,64}.
#   RR=96 -> 107 means r96 ALIASES r0; -> 100 means r96 is independent/phantom(=0).
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
    float t = x[gid];
    out[gid] = t + y[gid];
}
"""
def build():
    kp=os.path.join(HERE,"kernels","txy.metal"); open(kp,"w").write(SRC)
    arch=os.path.join(HERE,"txy.bin")
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    return kp,arch

if __name__=="__main__":
    kp,arch=build()
    buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    # locate loads (0x67) and the fadd (0x09 opsel 100)
    loads=[]; i=0; n=len(main)
    while i+14<=n:
        if main[i]==0x67: loads.append((i,main[i+4],main[i+8])); i+=14
        else: i+=2
    fadd=None; i=0
    while i+6<=n:
        if main[i]==0x09:
            length=8 if (main[i+2]&0x02) else 6
            if (main[i+2]&0x07)==0b100 and (main[i+4]>>7)==0: fadd=(i,length); break
            i+=length
        else: i+=2
    print("loads(off,slot,byte8):",[(o,s,hex(b)) for o,s,b in loads])
    print("fadd:",fadd, "bytes", main[fadd[0]:fadd[0]+fadd[1]].hex(), "byte+1=0x%02x srcA r%d"%(main[fadd[0]+1],main[fadd[0]+1]>>1))
    # x load = buffer(1) => slot==1
    xload=[o for o,s,b in loads if s==1]
    if not xload: print("no x load; loads slots:",[s for _,s,_ in loads]); sys.exit(1)
    xoff=xload[0]; xb8=[b for o,s,b in loads if o==xoff][0]
    print("x load off=%d byte+8=0x%02x (dst r%d)"%(xoff,xb8,xb8>>1))
    faoff=fadd[0]; fa_b1=main[faoff+1]; fa_size=fa_b1&1
    ld_flag=xb8&1
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
    base=int(loc[0])
    abs_ld=base+xoff+8; abs_fa=base+faoff+1
    xbf=os.path.join(HERE,"tx.bin"); ybf=os.path.join(HERE,"ty.bin")
    open(xbf,"wb").write(struct.pack("<f",7.0)); open(ybf,"wb").write(struct.pack("<f",100.0))
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    def run(WR,RR):
        spa=os.path.join(HERE,"td_sp.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f:
            f.seek(abs_ld); f.write(bytes([(WR<<1)|ld_flag]))
            f.seek(abs_fa); f.write(bytes([(RR<<1)|fa_size]))
        resp=r.request(archive=spa,grid=1,tg=1,ins={1:xbf,2:ybf},outs={0:4},timeout=8)
        v=struct.unpack_from('<f',resp["outs"][0],0)[0] if 0 in resp["outs"] and len(resp["outs"][0])>=4 else None
        return resp["status"],v
    print("\n WR RR  status   out   interp")
    for WR in [0, 32]:
        for RR in [WR, 95, 96, 97, 100, 127, (WR+96)]:
            if RR>127: continue
            st,v=run(WR,RR)
            interp=""
            if st=="OK" and v is not None:
                if abs(v-107)<1e-3: interp="x+y -> RR aliases WR(r%d)"%WR
                elif abs(v-100)<1e-3: interp="0+y -> RR independent(=0)"
                else: interp="out-100=%.4f"%(v-100)
            print(" %-3d %-3d %-8s %-6s %s"%(WR,RR,st,v,interp))
    r.close()
