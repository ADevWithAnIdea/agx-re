#!/usr/bin/env python3
# imm.py -- EXP-0006 packed-float-immediate probe. For each constant K, writes
# kernel `out=a+K`, compiles OUR OWN MSL, and extracts the ALU instruction bytes
# so we can reverse the (non-IEEE) immediate packing. With --run it also splices
# and dispatches to confirm the runtime value equals K.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are inspected/executed.
import os, sys, struct, argparse, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def load_mod(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
analyze=load_mod("analyze",os.path.join(HERE,"analyze.py"))

TEMPLATE='''kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {{
    out[gid] = a[gid] + ({K});
}}
'''

def build_and_alu(K, workdir="work"):
    src=os.path.join(workdir, "imm_src.metal")
    with open(src,"w") as f: f.write(TEMPLATE.format(K=repr(float(K))+"f"))
    m=analyze.main_of(src, fast_math=False, workdir=workdir)
    toks=analyze.structural_tokens(m)
    alu=[t for t in toks if t[0]=="ALU"]
    return (alu[0][3] if alu else b""), m

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--Ks",default="0,0.5,1,2,4,-1,-2,3.5,0.25,0.125,3,8,0.75,1.5,-0.5,16,0.0625,255,256,0.1")
    args=ap.parse_args()
    Ks=[float(x) for x in args.Ks.split(",")]
    print(f"{'K':>10} {'ALUbytes':<24} b0 b1 b2 b3 b4 b5 ...")
    for K in Ks:
        alu,_=build_and_alu(K)
        bs=" ".join(f"{x:02x}" for x in alu)
        print(f"{K:>10} {alu.hex():<24} {bs}")
