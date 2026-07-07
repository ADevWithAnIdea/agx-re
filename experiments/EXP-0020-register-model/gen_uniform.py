#!/usr/bin/env python3
# Uniform-register-file probes (runs ON DEVICE). Generates contrast kernels and
# dumps _agc.main + the metadata uniform/GPR footprint fields.
# CLEAN-ROOM: OWN-SHADER.
import os, subprocess, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
AMP=chr(38)

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

def all_meta_fields(buf,mo):
    s=mo.find_section("__TEXT","__compute"); nb=mo.base+s["offset"]; nm=ap.MachO(buf,nb)
    meta=None
    for sec in nm.sections:
        if sec["seg"]=="__GPU_METADATA":
            o=nb+sec["offset"]; meta=bytes(buf[o:o+sec["size"]])
    root=struct.unpack_from('<I',meta,0)[0]; rf=table_fields(meta,root)
    sub=rf[0]+struct.unpack_from('<I',meta,rf[0])[0]; ff=table_fields(meta,sub)
    return {i:(struct.unpack_from('<I',meta,p)[0] if p+4<=len(meta) else meta[p]) for i,p in ff.items()}

def dump(name, src):
    kp=os.path.join(HERE,"kernels",name+".metal"); open(kp,"w").write(src)
    arch=os.path.join(HERE,name+".bin")
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    if not os.path.exists(arch): return None,None
    buf=open(arch,"rb").read(); mo=gpu(buf)
    _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    mf=all_meta_fields(buf,mo); os.remove(arch)
    return main.hex(), mf

K={}
K["f_gpr"]="""#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* a [[buffer(1)]],
              device const float* b [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid]; }
"""
K["f_uni"]="""#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], constant float%s x [[buffer(1)]],
              constant float%s y [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = x + y; }
"""%(AMP,AMP)
K["i_subua"]="""#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
              constant int%s y [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = y - a[gid]; }
"""%AMP   # y in srcA (non-commutative)
K["i_subau"]="""#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
              constant int%s y [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] - y; }
"""%AMP   # y in srcB
# many uniforms summed -> uniform register indexing
def many(n):
    L=["#include <metal_stdlib>","using namespace metal;","kernel void k(device int* out [[buffer(0)]],"]
    for i in range(n): L.append("  constant int%s u%d [[buffer(%d)]],"%(AMP,i,i+1))
    L.append("  uint gid [[thread_position_in_grid]]) {")
    L.append("  out[gid] = "+"+".join("u%d"%i for i in range(n))+"; }")
    return "\n".join(L)
K["u_many8"]=many(8)
K["u_many16"]=many(16)

if __name__=="__main__":
    for name in ["f_gpr","f_uni","i_subua","i_subau","u_many8","u_many16"]:
        h,mf=dump(name,K[name])
        print("=== %s ==="%name)
        print(h)
        print("meta_fields:", {i:(v if v<100000 else hex(v)) for i,v in sorted(mf.items())} if mf else None)
        print()
