#!/usr/bin/env python3
"""Pilot 7 (NOT gated): why does the two-store read-back zero for D=0?"""
import struct, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]; REPO=EXP.parents[1]
for p in ("tools/agx-isa","tools/shdump","tools/agxtest"): sys.path.insert(0,str(REPO/p))
sys.path.insert(0,str(EXP/"harness"))
import agxparse, isa_helpers as H
from persistrun import PersistRunner
BIN=EXP/"work"/"bin"; K=EXP/"kernels"; SRC=K/"carrier_uni.metal"
buf=(HERE/"cu.bin").read_bytes(); roff,_=agxparse.locate_region(buf,"_agc.main")
_,pc=agxparse.extract_agx(buf); ML=len(pc["_agc.main"])
INS={1:str(HERE/"mm.bin"),2:str(HERE/"uu0.bin"),3:str(HERE/"uu1.bin"),4:str(HERE/"uu2.bin"),5:str(HERE/"uu3.bin")}
r=PersistRunner(source=str(SRC),function="k",fast_math=False,agxrun_persist=str(BIN/"agxrun_persist"))
sp=HERE/"sp7.bin"
def run(ins,n=3):
    prog=H.build_program(ins,ML); b=bytearray(buf); b[roff:roff+ML]=prog; sp.write_bytes(bytes(b))
    outs=[]
    for _ in range(n):
        resp=r.request(archive=str(sp),grid=1,tg=1,ins=INS,outs={0:12},timeout=8)
        outs.append(resp["status"] if resp["status"]!="OK" else
                    [struct.unpack_from("<i",resp["outs"][0],4*i)[0] for i in range(3)])
    return outs
for D,idx,ctrl in ((0,15,14),(1,15,14),(0,13,14),(2,15,14)):
    ins=[H.mov_imm(j,7) for j in range(16)]+[H.mov_imm(D,99),
         H.mov_imm(idx,0),H.device_store(idx,0,0,data_reg=D),
         H.mov_imm(idx,1),H.device_store(idx,0,0,data_reg=ctrl),H.stop()]
    print("two-store D=%2d idx=%2d ctrl=%2d ->"%(D,idx,ctrl), run(ins))
for D,idx in ((0,15),(0,13)):
    ins=[H.mov_imm(j,7) for j in range(16)]+[H.mov_imm(D,99),
         H.mov_imm(idx,0),H.device_store(idx,0,0,data_reg=D),H.stop()]
    print("one-store D=%2d idx=%2d ->"%(D,idx), run(ins))
# separate index registers for the two stores
for D in (0,1,2):
    ins=[H.mov_imm(j,7) for j in range(16)]+[H.mov_imm(D,99),
         H.mov_imm(15,0),H.mov_imm(13,1),
         H.device_store(15,0,0,data_reg=D),
         H.device_store(13,0,0,data_reg=14),H.stop()]
    print("two-store distinct-idx D=%2d ->"%D, run(ins))
r.close()
