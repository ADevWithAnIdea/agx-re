#!/usr/bin/env python3
# gprmeas.py — measure the GPR footprint of OUR OWN compute kernel via the
# compiler's __GPU_METADATA field-0 (same method as RT-12/b2_half.py).
# CLEAN-ROOM: OWN-SHADER. Only our own compiled shader's own metadata is read;
# no Apple binary is inspected.
#
# Usage:
#   gprmeas.py compile FILE.metal        -> prints "GPR <n>" for that source
#   gprmeas.py ladder                    -> generate ladder kernels, print N->GPR
import os, sys, subprocess, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py"))
ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def gpu(buf):
    for off,size,note in ap.iter_gpu_images(buf):
        try: mo=ap.MachO(buf,off)
        except ValueError: continue
        if mo.cputype==ap.APPLE_GPU_CPUTYPE: return mo
    return None

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
    if meta is None: return -1
    root=struct.unpack_from('<I',meta,0)[0]; rf=table_fields(meta,root)
    sub=rf[0]+struct.unpack_from('<I',meta,rf[0])[0]; ff=table_fields(meta,sub)
    f0=struct.unpack_from('<I',meta,ff[0])[0] if 0 in ff else -1
    return f0

def measure(path):
    r=subprocess.run(["./shdump","-o","/tmp/gm.bin",path],capture_output=True,cwd=HERE)
    if r.returncode!=0:
        sys.stderr.write(r.stderr.decode()); return None
    buf=bytearray(open("/tmp/gm.bin","rb").read()); mo=gpu(buf)
    if mo is None: return None
    return regfoot(buf,mo)

# Ladder kernel: N independent float accumulators kept live across a short loop,
# summed into the output (survives DCE). GPR footprint grows ~1 per accumulator.
def kernel_src_f(N,E=0):
    # PURE-FLOAT: N independent accumulator chains (live across loop) + E extra
    # independent live floats (loaded, kept live across loop, summed at end).
    # f0 grows ~1 per chain and ~1 per extra -> fine pure-float GPR control.
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device const float* a [[buffer(0)]],",
       "              device float* o [[buffer(1)]],",
       "              uint i [[thread_position_in_grid]]) {",
       "  float x=a[i];",
       "  float t=a[i+1]*1.000001f;"]
    for k in range(N): L.append("  float s%d=x*%.6ff+%.6ff;"%(k,1.001+0.001*k,0.5+0.01*k))
    for k in range(E): L.append("  float e%d=a[i+%d]*%.6ff;"%(k,3+k,1.0+0.001*k))
    L.append("  for(int j=0;j<6;j++){")
    for k in range(N): L.append("    s%d=fma(s%d,t,s%d*0.5f+%.6ff);"%(k,k,k,0.01*k))
    L.append("  }")
    terms=["s%d"%k for k in range(N)]+["e%d"%k for k in range(E)]
    if not terms: terms=["x"]
    L.append("  o[i]="+"+".join(terms)+";")
    L.append("}")
    return "\n".join(L)+"\n"

def kernel_src(N,H=0):
    # N INDEPENDENT float accumulator chains + H INDEPENDENT half chains, each
    # live across the loop (no cross-coupling) -> GPR grows ~1 per float chain,
    # ~0.5 per half chain (halves pack 2/GPR), for fine footprint control.
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device const float* a [[buffer(0)]],",
       "              device float* o [[buffer(1)]],",
       "              uint i [[thread_position_in_grid]]) {",
       "  float x=a[i];",
       "  float t=a[i+1]*1.000001f;",
       "  half ht=(half)(a[i+2]*0.5f);"]
    for k in range(N): L.append("  float s%d=x*%.6ff+%.6ff;"%(k,1.001+0.001*k,0.5+0.01*k))
    for k in range(H): L.append("  half h%d=(half)(x*%.4ff);"%(k,0.7+0.03*k))
    L.append("  for(int j=0;j<6;j++){")
    for k in range(N): L.append("    s%d=fma(s%d,t,s%d*0.5f+%.6ff);"%(k,k,k,0.01*k))
    for k in range(H): L.append("    h%d=fma(h%d,ht,h%d*(half)0.5h+(half)%.4fh);"%(k,k,k,0.01*k))
    L.append("  }")
    terms=["s%d"%k for k in range(N)]+["(float)h%d"%k for k in range(H)]
    if not terms: terms=["x"]
    L.append("  o[i]="+"+".join(terms)+";")
    L.append("}")
    return "\n".join(L)+"\n"

if __name__=="__main__":
    if sys.argv[1]=="compile":
        v=measure(sys.argv[2]); print("GPR",v)
    elif sys.argv[1]=="ladder":
        for N in range(1,25):
            open("/tmp/lad.metal","w").write(kernel_src(N))
            v=measure("/tmp/lad.metal")
            print(f"N={N:<3} GPR={v}")
