#!/usr/bin/env python3
# RT-7 Task 5 (b): HW-splice validation of compute SR codes. Base out[gid]=simd_lane_id
# has TWO get_sr: address (byte1=0xa0, tpig) + value (byte1=0x82, lane). Splice ONLY the
# value get_sr => each thread still writes to its correct out[gid], value = spliced SR.
# Dispatch grid=128 tg=64 and classify the output vector against every known SR pattern.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE)
from persistrun import PersistRunner
GRID=128; TG=64; SW=32
SRC="""#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint v [[thread_index_in_simdgroup]],
              uint gid [[thread_position_in_grid]]) { out[gid]=v; }
"""
PATS={
 "tpig.x(0..127)":lambda g:g,
 "pos_in_tg/tidx(0..63)":lambda g:g%TG,
 "simd_lane(0..31)":lambda g:g%SW,
 "simd_group(0/1 per tg)":lambda g:(g%TG)//SW,
 "threads_per_tg(=64)":lambda g:TG,
 "tgroup_pos(0/1)":lambda g:g//TG,
 "tgroups_per_grid(=2)":lambda g:GRID//TG,
 "threads_per_simdgroup(=32)":lambda g:SW,
 "const0":lambda g:0,
}
def classify(vec):
    L=[n for n,f in PATS.items() if all(vec[g]==f(g) for g in range(GRID))]
    return L if L else ["<no-match> "+str(vec[:4])+"|"+str(vec[30:36])+"|"+str(vec[64:68])]
def find_getsr(main):
    hits=[];i=0;n=len(main)
    while i+4<=n:
        if (main[i]&0x07)==0x04 and main[i+2]==0x10 and main[i+3]==0x06:
            hits.append((i,main[i+1])); i+=4; continue
        if main[i] in (0x67,0xe7): i+=14
        elif main[i]==0x0e: i+=4
        else: i+=2
    return hits
CANDS=[("thread_position_in_grid.x",0xa0),("thread_position_in_threadgroup.x",0xa4),
 ("thread_index_in_threadgroup",0xa7),("threads_per_threadgroup.x",0x98),
 ("threadgroup_position_in_grid.x",0x9c),("threadgroups_per_grid.x",0xa8),
 ("simd_lane_id",0x82),("simd_group_id",0x85)]
if __name__=="__main__":
    kp=os.path.join(HERE,"kernels","srb.metal"); open(kp,"w").write(SRC)
    arch=os.path.join(HERE,"srb.bin")
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    hits=find_getsr(main); print("get_sr:",[(h[0],hex(h[1])) for h in hits])
    val=[h for h in hits if h[1]==0x82]
    if not val: sys.exit("value get_sr (0x82) not found")
    off=val[0][0]; print("value get_sr off=%d (byte1=0x82)"%off)
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
    abs1=int(loc[0])+off+1
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    resp=r.request(archive=arch,grid=GRID,tg=TG,ins={},outs={0:GRID*4},timeout=8)
    vec=[struct.unpack_from('<I',resp["outs"][0],4*g)[0] for g in range(GRID)]
    print("baseline (simd_lane) ->",classify(vec))
    print("\n%-38s %-6s %-8s %s"%("splice byte1 =>","code","status","OBSERVED"))
    for name,code in CANDS:
        spa=os.path.join(HERE,"srb_sp.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([code]))
        resp=r.request(archive=spa,grid=GRID,tg=TG,ins={},outs={0:GRID*4},timeout=8)
        if resp["status"]!="OK": print("%-38s 0x%02x  %-8s -"%(name,code,resp["status"])); continue
        vec=[struct.unpack_from('<I',resp["outs"][0],4*g)[0] for g in range(GRID)]
        print("%-38s 0x%02x  %-8s %s"%(name,code,resp["status"],classify(vec)))
    r.close()
