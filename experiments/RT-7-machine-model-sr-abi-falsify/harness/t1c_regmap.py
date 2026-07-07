#!/usr/bin/env python3
# RT-7 Task 1b (v3): map physical GPR file & r96+ behaviour using the RT-1a
# HW-VALIDATED device_load index-register field (byte+5 of 0x67; 0x00->r0,...).
# Kernel builds K distinct KNOWN index regs idx_k = 1000+k, keeps them all live
# via an XOR checksum, and does ONE gather out[gid]=a[idx_0] with a[i]=i (ramp).
# Splicing that load's byte+5 = R makes out[gid] = a[content(phys reg R)] =
# content(R). Reading back which idx_k lands in each physical reg reveals the
# valid register range and whether r96..r127 alias / read 0 / fault (OOB).
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE)
from persistrun import PersistRunner

K=int(os.environ.get("K","94"))
ASIZE=1<<20

def kernel_src(K):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device uint* out [[buffer(0)]],",
       "              device const uint* a [[buffer(1)]],",
       "              device const uint* base [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    L.append("  uint bb = base[gid];")
    for k in range(K): L.append("  uint i%d = bb + %du;"%(k,1000+k))
    # keep every i_k live via a checksum used AFTER the gather
    L.append("  uint chk = 0u;")
    for k in range(K): L.append("  chk ^= i%d;"%k)
    L.append("  uint g = a[i0];")           # THE gather (only buffer-1 load)
    L.append("  out[gid*2+0] = g;")
    L.append("  out[gid*2+1] = chk;")
    L.append("}")
    return "\n".join(L)+"\n"

def build(K):
    src=kernel_src(K); kp=os.path.join(HERE,"kernels","gmap%d.metal"%K)
    open(kp,"w").write(src)
    arch=os.path.join(HERE,"gmap_%d.bin"%K)
    r=subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True,text=True)
    return kp,arch,r.stderr

def find_gather(main):
    # 0x67 load with base_slot(byte+4)==1  (buffer a).  return list of (off, byte5)
    hits=[]; i=0; n=len(main)
    while i+14<=n:
        if main[i] in (0x67,0xe7):
            if main[i]==0x67 and main[i+4]==1: hits.append((i,main[i+5],main[i:i+14].hex()))
            i+=14
        else: i+=2
    return hits

if __name__=="__main__":
    kp,arch,err=build(K)
    if not os.path.exists(arch): print("COMPILE_FAIL",err[-300:]); sys.exit(1)
    buf=open(arch,"rb").read()
    _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    hits=find_gather(main)
    print("MAIN_LEN",len(main),"buf1_loads",[(h[0],hex(h[1])) for h in hits])
    for h in hits: print("  gather off=%d byte5=0x%02x %s"%(h[0],h[1],h[2]))
    if not hits: print("NO GATHER FOUND"); sys.exit(1)
    goff,b5,_=hits[0]; flag=b5&0x80
    print("using gather off=%d orig byte5=0x%02x (idxreg r%d, flag0x%02x)"%(goff,b5,b5&0x7f,flag))
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
    abs_main=int(loc[0]); splice_abs=abs_main+goff+5
    abuf=os.path.join(HERE,"gm_a.bin"); bbuf=os.path.join(HERE,"gm_b.bin")
    # a[i]=i ramp
    with open(abuf,"wb") as f:
        f.write(b"".join(struct.pack("<I",i) for i in range(ASIZE)))
    open(bbuf,"wb").write(struct.pack("<I",0))   # base=0 -> idx_k = 1000+k
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    print("device",r.device)
    results={}
    for R in range(0,128):
        spa=os.path.join(HERE,"gm_spliced.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f:
            f.seek(splice_abs); f.write(bytes([R|flag]))
        resp=r.request(archive=spa,grid=1,tg=1,ins={1:abuf,2:bbuf},outs={0:8},timeout=8)
        val=None
        if 0 in resp["outs"] and len(resp["outs"][0])>=4:
            val=struct.unpack_from('<I',resp["outs"][0],0)[0]
        results[R]=(resp["status"],val)
        print("R=%-3d status=%-10s a[content(R)]=%s"%(R,resp["status"],val))
        sys.stdout.flush()
    r.close()
    print("\n=== SUMMARY (content(R) = readback value; idx_k=1000+k) ===")
    for R in range(0,128):
        s,v=results[R]
        tag=""
        if s=="OK" and v is not None and 1000<=v<1000+K: tag="=idx_%d"%(v-1000)
        elif s=="OK" and v==0: tag="(zero)"
        elif s!="OK": tag="FAULT"
        print("R=%-3d %-8s %s %s"%(R,s,v,tag))
