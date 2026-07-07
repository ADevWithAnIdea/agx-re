#!/usr/bin/env python3
# RT-7 Task 1a: falsify "96 addressable 32-bit GPRs" via a FINE metadata sweep.
# For each K live int regs: read the compiler's own __GPU_METADATA GPR footprint
# (f0) and scratch bytes, and run n=1 (loop no-op -> out[k]=in[k]) for HW correctness.
# CLEAN-ROOM: OWN-SHADER -- our own MSL, our own archive's own metadata.
import os, sys, subprocess, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def kernel_src(K):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device int* out [[buffer(0)]],",
       "              device const int* in [[buffer(1)]],",
       "              constant uint& n [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  int a%d = in[gid*%d+%d];"%(k,K,k))
    L.append("  for (uint i=1;i<n;i++) {")
    L.append("    int t = in[i];")
    for k in range(K): L.append("    a%d = a%d*t + a%d;"%(k,k,(k+1)%K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d] = a%d;"%(K,k,k))
    L.append("}")
    return "\n".join(L)+"\n"

def gpu(buf):
    for off,size,note in ap.iter_gpu_images(buf):
        try: mo=ap.MachO(buf,off)
        except ValueError: continue
        if mo.cputype==ap.APPLE_GPU_CPUTYPE: return mo

def table_fields(buf,tpos):
    soff=struct.unpack_from('<i',buf,tpos)[0]; vt=tpos-soff
    nf=(struct.unpack_from('<H',buf,vt)[0]-4)//2; f={}
    for i in range(nf):
        fo=struct.unpack_from('<H',buf,vt+4+i*2)[0]
        if fo: f[i]=tpos+fo
    return f

def regfoot_scratch(buf,mo):
    s=mo.find_section("__TEXT","__compute"); nb=mo.base+s["offset"]; nm=ap.MachO(buf,nb)
    meta=None
    for sec in nm.sections:
        if sec["seg"]=="__GPU_METADATA":
            o=nb+sec["offset"]; meta=bytes(buf[o:o+sec["size"]])
    root=struct.unpack_from('<I',meta,0)[0]; rf=table_fields(meta,root)
    sub=rf[0]+struct.unpack_from('<I',meta,rf[0])[0]; ff=table_fields(meta,sub)
    f0=struct.unpack_from('<I',meta,ff[0])[0] if 0 in ff else -1
    sc=0
    for fi in (41,14):
        if fi in ff:
            sc=struct.unpack_from('<I',meta,ff[fi])[0]; break
    return f0,sc,sorted(ff.keys())

def maxreg_ls(main):
    mx=-1; i=0; n=len(main)
    while i+14<=n:
        if main[i] in (0x67,0xe7):
            reg=main[i+8]>>1
            if reg>mx: mx=reg
            i+=14
        else: i+=2
    return mx

def build(K):
    src=kernel_src(K); kp=os.path.join(HERE,"kernels","pi%d.metal"%K)
    open(kp,"w").write(src)
    arch=os.path.join(HERE,"pi_%d.bin"%K)
    r=subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True,text=True)
    return kp,arch,r.stderr

if __name__=="__main__":
    Ks=[int(x) for x in sys.argv[1:]] if len(sys.argv)>1 else list(range(60,86))+[88,92,96,104,128,192,256]
    print("%-5s %-8s %-6s %-8s %-8s %-8s %s"%("K","f0","scr","maxreg","status","copy","meta_fields"))
    for K in Ks:
        kp,arch,err=build(K)
        if not os.path.exists(arch): print("K=%d COMPILE_FAIL %s"%(K,err[-120:])); continue
        buf=open(arch,"rb").read(); mo=gpu(buf)
        _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
        f0,scr,fields=regfoot_scratch(buf,mo); mx=maxreg_ls(main)
        inbuf=os.path.join(HERE,"pin.bin"); nbuf=os.path.join(HERE,"pn.bin")
        vals=list(range(1,K+1))
        open(inbuf,"wb").write(b"".join(struct.pack("<i",v) for v in vals))
        open(nbuf,"wb").write(struct.pack("<I",1))
        st="?"; got=None
        try:
            r=subprocess.run([os.path.join(HERE,"agxrun"),"--archive",arch,"--source",kp,
                              "--function","k","--no-fast-math","--grid","1","--tg","1",
                              "--buf","1=%s"%inbuf,"--buf","2=%s"%nbuf,"--out","0=%d"%(K*4)],
                             capture_output=True,text=True,timeout=30)
            for ln in r.stdout.splitlines():
                if ln.startswith("STATUS "): st=ln.split()[1]
                if ln.startswith("OUT 0 "):
                    bb=bytes.fromhex(ln.split(None,2)[2]); got=[struct.unpack_from('<i',bb,j)[0] for j in range(0,len(bb),4)]
        except subprocess.TimeoutExpired: st="HANG"
        ok="PASS" if got==vals else ("FAIL" if got is not None else "NORES")
        print("%-5d %-8d %-6d %-8d %-8s %-8s %s"%(K,f0,scr,mx,st,ok,fields))
        os.remove(arch); sys.stdout.flush()
