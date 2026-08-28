#!/usr/bin/env python3
"""Pilot 2 (NOT gated evidence): probe the uniform file through carrier_uni."""
import struct, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]; REPO = EXP.parents[1]
sys.path.insert(0, str(REPO/"tools"/"agx-isa")); sys.path.insert(0, str(REPO/"tools"/"shdump"))
sys.path.insert(0, str(REPO/"tools"/"agxtest")); sys.path.insert(0, str(EXP/"harness"))
import isadb, agxparse, isa_helpers as H
from persistrun import PersistRunner
BIN = EXP/"work"/"bin"; K = EXP/"kernels"
SRC = K/"carrier_uni.metal"
arch = HERE/"carrier_uni.bin"
subprocess.run([str(BIN/"shdump"),"-o",str(arch),"--no-fast-math",str(SRC),"-f","k"],check=True,capture_output=True)
buf = arch.read_bytes()
roff, rlen = agxparse.locate_region(buf,"_agc.main")
_, pieces = agxparse.extract_agx(buf)
MAIN_LEN = len(pieces["_agc.main"])
print("main_len", MAIN_LEN, "roff", roff)

MAG = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
for i,v in enumerate(MAG):
    (HERE/("u%d.bin"%i)).write_bytes(struct.pack("<I", v))
(HERE/"mem.bin").write_bytes(b"".join(struct.pack("<i", 1000+i) for i in range(16)))
INS = {1:str(HERE/"mem.bin"), 2:str(HERE/"u0.bin"), 3:str(HERE/"u1.bin"),
       4:str(HERE/"u2.bin"), 5:str(HERE/"u3.bin")}

def prog_unimov(D, U, idx=15):
    ins = [H.mov_imm(j, 7) for j in range(16)]
    ins.append(H.mov_imm(idx, 0))
    ins.append(H.regmove(D, U, 0x01, 0x08))
    ins.append(H.device_store(idx, 0, 0, data_reg=D))
    ins.append(H.stop())
    return H.build_program(ins, MAIN_LEN)

r = PersistRunner(source=str(SRC), function="k", fast_math=False,
                  agxrun_persist=str(BIN/"agxrun_persist"))
print("READY", r.device)
sp = HERE/"sp.bin"
found = {}
for U in range(0, 256):
    p = prog_unimov(3, U)
    b = bytearray(buf); b[roff:roff+MAIN_LEN] = p
    sp.write_bytes(bytes(b))
    resp = r.request(archive=str(sp), grid=1, tg=1, ins=INS, outs={0:8}, timeout=8)
    if resp["status"] != "OK":
        print("U=%3d %s" % (U, resp["status"])); continue
    v = struct.unpack_from("<I", resp["outs"][0], 0)[0]
    if v != 7:
        print("U=%3d (0x%02x)  -> 0x%08x" % (U, U, v))
    found[U]=v
r.close()
import collections
c = collections.Counter(found.values())
print("distinct values:", len(c))
for v,n in c.most_common(12): print("   0x%08x  x%d" % (v,n))
