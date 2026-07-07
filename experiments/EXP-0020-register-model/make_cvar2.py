#!/usr/bin/env python3
# Build cvar2.m: cvar.m + graded-pressure "heavy-style" kernels (2 device buffers,
# no uniforms -> cvar-compatible) so we can capture the launch-descriptor config
# word vs register footprint. Also writes each kernel as a .metal for f0 measurement.
# CLEAN-ROOM: OWN-SHADER (our own kernels) + reuse of our EXP-0011 harness + iotrace.
import os
HERE=os.path.dirname(os.path.abspath(__file__))
Ns=[4,8,24,48,72,96,128,160]

def msl(N):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device const float* a [[buffer(0)]],",
       "              device float* o [[buffer(1)]],",
       "              uint i [[thread_position_in_grid]]) {",
       "  float x=a[i];"]
    for k in range(N): L.append("  float v%d=x+%d.0f;"%(k,k+1))
    L.append("  for(int j=0;j<3;j++){")
    for k in range(N): L.append("    v%d=fma(v%d,v%d,v%d);"%(k,k,(k+1)%N,(k+2)%N))
    L.append("  }")
    L.append("  o[i]="+"+".join("v%d"%k for k in range(N))+";")
    L.append("}")
    return "\n".join(L)+"\n"

def c_entry(N):
    body=msl(N).replace("\\","\\\\").replace('"','\\"').replace("\n","\\n")
    return '  { "h%d",\n    "%s",\n    2, 0, 0, 0 },\n'%(N,body)

if __name__=="__main__":
    src=open(os.path.join(HERE,"cvar.m")).read()
    entries="".join(c_entry(N) for N in Ns)
    # insert before the terminating '};' of the KERNELS[] array (first '};' after KERNELS)
    idx=src.index("static const Kernel KERNELS[]")
    end=src.index("\n};",idx)
    src2=src[:end]+"\n"+entries+src[end+1:]
    open(os.path.join(HERE,"cvar2.m"),"w").write(src2)
    for N in Ns:
        open(os.path.join(HERE,"kernels","h%d.metal"%N),"w").write(msl(N))
    print("wrote cvar2.m and %d kernels"%len(Ns))
