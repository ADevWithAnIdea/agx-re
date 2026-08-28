#!/usr/bin/env python3
"""Pilot 5 (NOT gated): isolate the D=0/6/14 CMDBUF_ERROR seen in the smoke run."""
import struct, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]; REPO=EXP.parents[1]
for p in ("tools/agx-isa","tools/shdump","tools/agxtest"): sys.path.insert(0,str(REPO/p))
sys.path.insert(0,str(EXP/"harness"))
import isadb, agxparse, isa_helpers as H
from persistrun import PersistRunner
BIN=EXP/"work"/"bin"; K=EXP/"kernels"; SRC=K/"carrier_uni.metal"
arch=HERE/"cu.bin"
subprocess.run([str(BIN/"shdump"),"-o",str(arch),"--no-fast-math",str(SRC),"-f","k"],check=True,capture_output=True)
buf=arch.read_bytes(); roff,_=agxparse.locate_region(buf,"_agc.main")
_,pc=agxparse.extract_agx(buf); ML=len(pc["_agc.main"])
for i,v in enumerate((0xA1B2C3D4,0x1E2F3040,0x55AA33CC,0x0F1E2D3C)):
    (HERE/("uu%d.bin"%i)).write_bytes(struct.pack("<I",v))
(HERE/"mm.bin").write_bytes(b"".join(struct.pack("<i",1000+i) for i in range(64)))
INS={1:str(HERE/"mm.bin"),2:str(HERE/"uu0.bin"),3:str(HERE/"uu1.bin"),4:str(HERE/"uu2.bin"),5:str(HERE/"uu3.bin")}
r=PersistRunner(source=str(SRC),function="k",fast_math=False,agxrun_persist=str(BIN/"agxrun_persist"))
sp=HERE/"sp5.bin"
def run(instrs, nout=8):
    prog=H.build_program(instrs, ML)
    b=bytearray(buf); b[roff:roff+ML]=prog; sp.write_bytes(bytes(b))
    resp=r.request(archive=str(sp),grid=1,tg=1,ins=INS,outs={0:nout},timeout=8)
    if resp["status"]!="OK": return resp["status"], None
    return "OK", [struct.unpack_from("<i",resp["outs"][0],4*i)[0] for i in range(nout//4)]
print("--- A: single store, data_reg=D, idx=15")
for D in range(16):
    if D==15: continue
    ins=[H.mov_imm(j,7) for j in range(16)]+[H.mov_imm(D,99),H.mov_imm(15,0),
         H.device_store(15,0,0,data_reg=D),H.stop()]
    print(" D=%2d ext=0x%02x %s"%(D,2*D,run(ins)))
print("--- B: single store, data_reg fixed=1, idx=15, vary D only")
for D in range(16):
    if D in (1,15): continue
    ins=[H.mov_imm(j,7) for j in range(16)]+[H.mov_imm(D,99),H.mov_imm(15,0),
         H.device_store(15,0,0,data_reg=1),H.stop()]
    print(" D=%2d %s"%(D,run(ins)))
print("--- C: single store, vary data_reg with no mov_imm test")
for R in range(16):
    ins=[H.mov_imm(j,20+j) for j in range(16)]+[H.mov_imm(15,0),
         H.device_store(15,0,0,data_reg=R),H.stop()]
    print(" R=%2d ext=0x%02x %s"%(R,2*R,run(ins)))
r.close()
