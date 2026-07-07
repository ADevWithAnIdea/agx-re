#!/usr/bin/env python3
# RT-7 Task 5 (a): read off the compiler's OWN get_sr byte1 for each builtin.
# One kernel per builtin storing to out[0] (constant addr) => exactly ONE get_sr;
# its byte1 = that builtin's SR code. Compare to the documented table -> any
# mismatch is a MISLABEL. CLEAN-ROOM: OWN-SHADER (byte observation).
import os, sys, subprocess, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

# builtin -> (argdecl, expr, documented_code)
COMPUTE=[
 ("thread_position_in_grid.x","uint3 v [[thread_position_in_grid]]","v.x",0xa0),
 ("thread_position_in_grid.y","uint3 v [[thread_position_in_grid]]","v.y",0xa1),
 ("thread_position_in_grid.z","uint3 v [[thread_position_in_grid]]","v.z",0xa2),
 ("thread_position_in_threadgroup.x","uint3 v [[thread_position_in_threadgroup]]","v.x",0xa4),
 ("thread_position_in_threadgroup.y","uint3 v [[thread_position_in_threadgroup]]","v.y",0xa5),
 ("thread_position_in_threadgroup.z","uint3 v [[thread_position_in_threadgroup]]","v.z",0xa6),
 ("thread_index_in_threadgroup","uint v [[thread_index_in_threadgroup]]","v",0xa7),
 ("threadgroup_position_in_grid.x","uint3 v [[threadgroup_position_in_grid]]","v.x",0x9c),
 ("threadgroup_position_in_grid.y","uint3 v [[threadgroup_position_in_grid]]","v.y",0x9d),
 ("threadgroup_position_in_grid.z","uint3 v [[threadgroup_position_in_grid]]","v.z",0x9e),
 ("threads_per_threadgroup.x","uint3 v [[threads_per_threadgroup]]","v.x",0x98),
 ("threads_per_threadgroup.y","uint3 v [[threads_per_threadgroup]]","v.y",0x99),
 ("threads_per_threadgroup.z","uint3 v [[threads_per_threadgroup]]","v.z",0x9a),
 ("threadgroups_per_grid.x","uint3 v [[threadgroups_per_grid]]","v.x",0xa8),
 ("threadgroups_per_grid.y","uint3 v [[threadgroups_per_grid]]","v.y",0xa9),
 ("threadgroups_per_grid.z","uint3 v [[threadgroups_per_grid]]","v.z",0xaa),
 ("simd_lane_id (thread_index_in_simdgroup)","uint v [[thread_index_in_simdgroup]]","v",0x82),
 ("simd_group_id (simdgroup_index_in_threadgroup)","uint v [[simdgroup_index_in_threadgroup]]","v",0x85),
 ("threads_per_simdgroup","uint v [[threads_per_simdgroup]]","v",None),
]
def build(argdecl,expr):
    src=("#include <metal_stdlib>\nusing namespace metal;\n"
         "kernel void k(device uint* out [[buffer(0)]], %s) { out[0]=%s; }\n"%(argdecl,expr))
    kp=os.path.join(HERE,"kernels","srx.metal"); open(kp,"w").write(src)
    arch=os.path.join(HERE,"srx.bin")
    r=subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True,text=True)
    return arch,r.stderr

def find_getsr(main):
    # get_sr signature: byte0 low-nibble 0xc, byte2==0x10, byte3==0x06 (from observed 0c a0 10 06)
    # get_sr group = byte0 bits[0:3]==0b100 (so 0x04/0x0c/0x14/0x24/...); byte2/3 = suffix.
    hits=[]; i=0;n=len(main)
    while i+4<=n:
        if (main[i]&0x07)==0x04 and main[i+2]==0x10 and main[i+3]==0x06:
            hits.append((i,main[i],main[i+1])); i+=4; continue
        if main[i] in (0x67,0xe7): i+=14
        elif main[i]==0x0e: i+=4
        else: i+=2
    return hits

if __name__=="__main__":
    print("%-48s %-6s %-6s %s"%("builtin","doc","obs","verdict"))
    for name,argdecl,expr,doc in COMPUTE:
        arch,err=build(argdecl,expr)
        if not os.path.exists(arch): print("%-48s COMPILE_FAIL %s"%(name,err[-80:])); continue
        buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
        hits=find_getsr(main)
        codes=[h[2] for h in hits]
        docs="0x%02x"%doc if doc is not None else "folded"
        if not hits:
            obs="none"; verdict="FOLDED/computed (no get_sr) -- MAIN=%s"%main.hex()[:40]
        else:
            obs=",".join("0x%02x"%c for c in codes)
            if doc is None: verdict="expected folded but get_sr present!"
            elif len(codes)==1 and codes[0]==doc: verdict="CONFIRM"
            elif doc in codes: verdict="CONFIRM (+extra)"
            else: verdict=">>> MISLABEL? obs!=doc"
        print("%-48s %-6s %-6s %s"%(name,docs,obs,verdict))
        os.remove(arch)
