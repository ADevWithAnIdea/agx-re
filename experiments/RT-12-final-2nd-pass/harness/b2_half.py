#!/usr/bin/env python3
# b2_half.py -- RT-12 Part B: re-verify "16-bit halves packed 2 per GPR" via an INDEPENDENT
# register-footprint comparison. DIFFERENT kernel from RT-7's cyclic-FMA: a bank of K
# independent madd accumulators, compiled once as `half` and once as `float`; compare the
# compiler's own __GPU_METADATA GPR footprint (field 0). If halves pack 2/GPR, the half
# kernel's footprint is ~half the float kernel's.
# CLEAN-ROOM: OWN-SHADER (our MSL, our archive's own metadata). No Apple binary inspected.
import os, sys, subprocess, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py"))
ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def kernel_src(K, ty):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device %s* out [[buffer(0)]],"%ty,
       "              device const %s* in [[buffer(1)]],"%ty,
       "              constant uint& n [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  %s a%d = in[gid*%d+%d];"%(ty,k,K,k))
    L.append("  for (uint i=1;i<n;i++) {")
    L.append("    %s t = in[i];"%ty)
    for k in range(K): L.append("    a%d = a%d*t + a%d;"%(k,k,(k+3)%K))  # different mix than RT-7
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

def regfoot(buf,mo):
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
        if fi in ff: sc=struct.unpack_from('<I',meta,ff[fi])[0]; break
    return f0,sc

def compile_f0(K,ty):
    src=kernel_src(K,ty); open("/tmp/b2.metal","w").write(src)
    r=subprocess.run(["./shdump","-o","/tmp/b2.bin","/tmp/b2.metal"],capture_output=True)
    if r.returncode!=0: return None,None
    buf=bytearray(open("/tmp/b2.bin","rb").read()); mo=gpu(buf)
    return regfoot(buf,mo)

print("K   float_f0 float_sc   half_f0 half_sc   ratio(half/float)")
for K in [24,32,48,64]:
    ff,fs=compile_f0(K,"float"); hf,hs=compile_f0(K,"half")
    ratio = (hf/ff) if (ff and ff>0) else 0
    print(f"{K:<4}{ff:<9}{fs:<11}{hf:<9}{hs:<10}{ratio:.3f}")
