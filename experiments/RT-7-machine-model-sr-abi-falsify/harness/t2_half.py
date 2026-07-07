#!/usr/bin/env python3
# RT-7 Task 2: re-prove "16-bit halves pack 2-per-GPR" with a DIFFERENT kernel.
# Compare compiler GPR footprint f0 for K live `float` vs K live `half` accumulators.
# If halves pack 2/GPR, half-f0 ~= 0.5..0.6x float-f0 and 64 halves fit in ~50 GPRs.
# Uses an independent (non-cyclic) live-value structure: a_k depend on each other in
# a tree so all K stay live to K stores; run n=1 for correctness (out[k]=in[k]).
# CLEAN-ROOM: OWN-SHADER.
import os, sys, subprocess, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def kern(K,ty):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device %s* out [[buffer(0)]],"%ty,
       "              device const %s* in [[buffer(1)]],"%ty,
       "              constant uint& n [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  %s a%d = in[gid*%d+%d];"%(ty,k,K,k))
    L.append("  for (uint i=1;i<n;i++){ %s t=in[i];"%ty)
    for k in range(K): L.append("    a%d = a%d*t + a%d;"%(k,k,(k+1)%K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d]=a%d;"%(K,k,k))
    L.append("}")
    return "\n".join(L)+"\n"

def gpu(buf):
    for off,size,note in ap.iter_gpu_images(buf):
        try: mo=ap.MachO(buf,off)
        except ValueError: continue
        if mo.cputype==ap.APPLE_GPU_CPUTYPE: return mo
def tf(buf,tp):
    so=struct.unpack_from('<i',buf,tp)[0]; vt=tp-so; nf=(struct.unpack_from('<H',buf,vt)[0]-4)//2; f={}
    for i in range(nf):
        fo=struct.unpack_from('<H',buf,vt+4+i*2)[0]
        if fo: f[i]=tp+fo
    return f
def f0scr(buf,mo):
    s=mo.find_section("__TEXT","__compute"); nb=mo.base+s["offset"]; nm=ap.MachO(buf,nb); meta=None
    for sec in nm.sections:
        if sec["seg"]=="__GPU_METADATA": o=nb+sec["offset"]; meta=bytes(buf[o:o+sec["size"]])
    root=struct.unpack_from('<I',meta,0)[0]; rf=tf(meta,root); sub=rf[0]+struct.unpack_from('<I',meta,rf[0])[0]; ff=tf(meta,sub)
    f0=struct.unpack_from('<I',meta,ff[0])[0] if 0 in ff else -1
    scr=0
    for fi in (41,14):
        if fi in ff: scr=struct.unpack_from('<I',meta,ff[fi])[0]; break
    return f0,scr

def build(K,ty):
    kp=os.path.join(HERE,"kernels","hp_%s%d.metal"%(ty,K)); open(kp,"w").write(kern(K,ty))
    arch=os.path.join(HERE,"hp_%s%d.bin"%(ty,K))
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    return kp,arch

if __name__=="__main__":
    Ks=[int(x) for x in sys.argv[1:]] if len(sys.argv)>1 else [8,16,24,32,40,48,56,64,72,80,96,128,160,190]
    print("%-5s %-16s %-16s %-8s"%("K","float f0/scr","half f0/scr","ratio h/f"))
    for K in Ks:
        _,af=build(K,"float"); _,ah=build(K,"half")
        try:
            bf=open(af,"rb").read(); ff0,fscr=f0scr(bf,gpu(bf))
        except Exception as e: ff0,fscr=(-1,-1)
        try:
            bh=open(ah,"rb").read(); hf0,hscr=f0scr(bh,gpu(bh))
        except Exception as e: hf0,hscr=(-1,-1)
        ratio=("%.3f"%(hf0/ff0)) if ff0>0 and hf0>0 else "?"
        print("%-5d %-16s %-16s %-8s"%(K,"%d/%d"%(ff0,fscr),"%d/%d"%(hf0,hscr),ratio))
        for p in (af,ah):
            try: os.remove(p)
            except: pass
        sys.stdout.flush()
