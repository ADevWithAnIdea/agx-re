#!/usr/bin/env python3
# RT-7 Task 5: falsify the get_sr SR-number table (compute SRs) by SPLICING byte1.
# Base kernel: out[gid]=thread_index_in_threadgroup (single get_sr). Splice its
# byte1 to each candidate SR code, dispatch grid=128 tg=64, and CLASSIFY the output
# vector against the expected semantics of every known SR. Any code whose output
# does not match its documented meaning is a MISLABEL.
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
              uint v [[thread_index_in_threadgroup]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = v;
}
"""
def build():
    kp=os.path.join(HERE,"kernels","sr_base.metal"); open(kp,"w").write(SRC)
    arch=os.path.join(HERE,"sr_base.bin")
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    return kp,arch

# expected patterns as functions of gid
def pat_gid(g): return g
def pat_lid(g): return g%TG
def pat_lane(g): return g%SW
def pat_simdgrp(g): return (g%TG)//SW
def expected():
    E={}
    for g in range(GRID):
        pass
    return E
PATS={
 "tpig.x(0..127)":       lambda g:g,
 "pos_in_tg.x/tidx(0..63)":lambda g:g%TG,
 "simd_lane(0..31)":     lambda g:g%SW,
 "simd_group(0/1)":      lambda g:(g%TG)//SW,
 "threads_per_tg(=64)":  lambda g:TG,
 "tgroup_pos(0/1)":      lambda g:g//TG,
 "tgroups_per_grid(=2)": lambda g:GRID//TG,
 "threads_per_simdgroup(=32)": lambda g:SW,
 "const0":               lambda g:0,
}
def classify(vec):
    labels=[]
    for name,f in PATS.items():
        if all(vec[g]==f(g) for g in range(GRID)): labels.append(name)
    return labels if labels else ["<no-match> sample="+str(vec[:8])+"..."+str(vec[60:68])]

CANDIDATES = [
 ("thread_position_in_grid.x", 0xa0), ("...y",0xa1), ("...z",0xa2),
 ("thread_position_in_threadgroup.x", 0xa4), ("...y",0xa5), ("...z",0xa6),
 ("thread_index_in_threadgroup", 0xa7),
 ("threads_per_threadgroup.x", 0x98), ("...y",0x99), ("...z",0x9a),
 ("threadgroup_position_in_grid.x", 0x9c), ("...y",0x9d), ("...z",0x9e),
 ("threadgroups_per_grid.x", 0xa8), ("...y",0xa9), ("...z",0xaa),
 ("simd_lane_id", 0x82), ("simd_group_id", 0x85),
]
if __name__=="__main__":
    kp,arch=build()
    buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    # find get_sr: byte0 low-nibble 0xc, 4 bytes. There should be exactly one.
    getsr=[]; i=0;n=len(main)
    while i+4<=n:
        if (main[i]&0x0f)==0x0c:
            getsr.append((i,main[i],main[i+1],main[i+2],main[i+3])); i+=4
        elif main[i] in (0x67,0xe7): i+=14
        elif main[i]==0x0e: i+=4
        else: i+=2
    print("get_sr candidates (off,b0,b1,b2,b3):",[(g[0],hex(g[1]),hex(g[2]),hex(g[3]),hex(g[4])) for g in getsr])
    # pick the 4-byte get_sr whose b1 is the tidx code (0xa7); else first
    tgt=None
    for g in getsr:
        if g[2]==0xa7: tgt=g; break
    if tgt is None: tgt=getsr[0]
    off=tgt[0]; print("using get_sr at off=%d orig b1=0x%02x"%(off,tgt[2]))
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
    abs1=int(loc[0])+off+1
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    # baseline
    resp=r.request(archive=arch,grid=GRID,tg=TG,ins={},outs={0:GRID*4},timeout=8)
    vec=[struct.unpack_from('<I',resp["outs"][0],4*g)[0] for g in range(GRID)]
    print("BASELINE (unspliced, tidx) ->",classify(vec))
    print("\n%-38s %-6s %-8s %s"%("claimed builtin","code","status","OBSERVED semantics"))
    for name,code in CANDIDATES:
        spa=os.path.join(HERE,"sr_sp.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([code]))
        resp=r.request(archive=spa,grid=GRID,tg=TG,ins={},outs={0:GRID*4},timeout=8)
        if resp["status"]!="OK":
            print("%-38s 0x%02x  %-8s -"%(name,code,resp["status"])); continue
        vec=[struct.unpack_from('<I',resp["outs"][0],4*g)[0] for g in range(GRID)]
        print("%-38s 0x%02x  %-8s %s"%(name,code,resp["status"],classify(vec)))
    r.close()
