#!/usr/bin/env python3
# RT-7 Task 1b (v2): map the physical GPR file & test r96+ alias/fault.
# Kernel keeps K distinct KNOWN float values a_k=in[k]=k+1 live, plus ONE unique
# fmul probe = a0 * m (m=in2[gid]=1.0). The trailing sum forces all a_k live at
# the probe. srcA of the fmul (byte+1 = (reg<<1)|size, EXP-0006 validated) selects
# which physical GPR feeds the multiply; out[gid] = content(phys reg R) * 1.0.
# Sweep byte+1 => R=0..127 and read back content(R): reveals valid range, and
# whether r96..r127 ALIAS a live reg / read 0 / FAULT.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE)
from persistrun import PersistRunner

K=int(os.environ.get("K","90"))

def kernel_src(K):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device float* out [[buffer(0)]],",
       "              device const float* in [[buffer(1)]],",
       "              device const float* mm [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  float a%d = in[%d];"%(k,k))
    L.append("  float m = mm[gid];")
    L.append("  float probe = a0 * m;")          # the UNIQUE fmul
    L.append("  float s = 0.0;")
    for k in range(K): L.append("  s += a%d;"%k)  # fadd chain -> keeps a_k live
    L.append("  out[gid*2+0] = probe;")
    L.append("  out[gid*2+1] = s;")
    L.append("}")
    return "\n".join(L)+"\n"

def build(K):
    src=kernel_src(K); kp=os.path.join(HERE,"kernels","regmap%d.metal"%K)
    open(kp,"w").write(src)
    arch=os.path.join(HERE,"regmap_%d.bin"%K)
    r=subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True,text=True)
    return kp,arch,r.stderr

def find_fmul(main):
    # 0x09 float ALU; opsel = byte+2 low3; fmul==0b101. length 6 (or 8 if byte+2&2).
    hits=[]; i=0; n=len(main)
    while i+6<=n:
        if main[i]==0x09:
            opsel=main[i+2]&0x07
            length=8 if (main[i+2]&0x02) else 6
            if opsel==0b101: hits.append((i,length,main[i+1]))
            i+=length
        else:
            i+=2
    return hits

if __name__=="__main__":
    kp,arch,err=build(K)
    if not os.path.exists(arch): print("COMPILE_FAIL",err[-300:]); sys.exit(1)
    buf=open(arch,"rb").read()
    _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    hits=find_fmul(main)
    print("MAIN_LEN",len(main),"fmul_hits",[(h[0],h[1],hex(h[2])) for h in hits])
    if len(hits)!=1:
        print("WARN: expected exactly 1 fmul, got",len(hits));
    fmul_off,flen,b1=hits[0]
    srcA_reg=b1>>1; size=b1&1
    print("probe fmul at main-off %d, byte+1=0x%02x -> srcA r%d size%d"%(fmul_off,b1,srcA_reg,size))
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
    abs_main=int(loc[0]); splice_abs=abs_main+fmul_off+1
    print("archive splice byte offset =",splice_abs)
    # inputs
    inbuf=os.path.join(HERE,"rm_in.bin"); mbuf=os.path.join(HERE,"rm_m.bin")
    open(inbuf,"wb").write(b"".join(struct.pack("<f",k+1) for k in range(K)))
    open(mbuf,"wb").write(struct.pack("<f",1.0))
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    print("device",r.device)
    results={}
    for R in range(0,128):
        spa=os.path.join(HERE,"rm_spliced.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f:
            f.seek(splice_abs); f.write(bytes([(R<<1)|size]))
        resp=r.request(archive=spa,grid=1,tg=1,ins={1:inbuf,2:mbuf},outs={0:8},timeout=8)
        val=None
        if 0 in resp["outs"] and len(resp["outs"][0])>=4:
            val=struct.unpack_from('<f',resp["outs"][0],0)[0]
        results[R]=(resp["status"],val)
        print("R=%-3d status=%-10s content=%s"%(R,resp["status"],val))
        sys.stdout.flush()
    r.close()
    # summary
    print("\n=== SUMMARY ===")
    live={R:v for R,(s,v) in results.items() if s=="OK" and v not in (None,0.0)}
    print("orig srcA reg = r%d (should read a0=1.0)"%srcA_reg)
    print("valid (nonzero) content regs:", {R:v for R,v in sorted(live.items())})
    faults=[R for R,(s,v) in results.items() if s not in ("OK",)]
    print("non-OK (fault) regs:", faults)
