#!/usr/bin/env python3
"""Pilot 6 (NOT gated): is the CMDBUF_ERROR deterministic per program?"""
import struct, subprocess, sys, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]; REPO=EXP.parents[1]
for p in ("tools/agx-isa","tools/shdump","tools/agxtest"): sys.path.insert(0,str(REPO/p))
sys.path.insert(0,str(EXP/"harness"))
import agxparse, isa_helpers as H
from persistrun import PersistRunner
BIN=EXP/"work"/"bin"; K=EXP/"kernels"; SRC=K/"carrier_uni.metal"
arch=HERE/"cu.bin"
buf=arch.read_bytes(); roff,_=agxparse.locate_region(buf,"_agc.main")
_,pc=agxparse.extract_agx(buf); ML=len(pc["_agc.main"])
INS={1:str(HERE/"mm.bin"),2:str(HERE/"uu0.bin"),3:str(HERE/"uu1.bin"),4:str(HERE/"uu2.bin"),5:str(HERE/"uu3.bin")}
r=PersistRunner(source=str(SRC),function="k",fast_math=False,agxrun_persist=str(BIN/"agxrun_persist"))
sp=HERE/"sp6.bin"
def run(prog,tag):
    b=bytearray(buf); b[roff:roff+ML]=prog; sp.write_bytes(bytes(b))
    resp=r.request(archive=str(sp),grid=1,tg=1,ins=INS,outs={0:8},timeout=8)
    return resp["status"], resp.get("error")
for D in (0,7,14,3):
    ins=[H.mov_imm(j,7) for j in range(16)]+[H.mov_imm(D,99),H.mov_imm(15,0),
         H.device_store(15,0,0,data_reg=D),H.stop()]
    prog=H.build_program(ins,ML)
    outs=[run(prog,D) for _ in range(10)]
    print("D=%2d sha=%s"%(D,hashlib.sha256(prog).hexdigest()[:12]), [o[0] for o in outs])
    for o in outs:
        if o[0]!="OK": print("    err:", o[1]); break
r.close()
