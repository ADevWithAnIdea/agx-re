#!/usr/bin/env python3
"""Pilot 1 (NOT gated evidence): confirm the four carriers' baselines run and
match their host-computed oracles on the local M4, via the persistent runner."""
import struct, subprocess, sys, os
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO/"tools"/"agx-isa")); sys.path.insert(0, str(REPO/"tools"/"shdump"))
sys.path.insert(0, str(REPO/"tools"/"agxtest"))
import isadb, agxparse
from persistrun import PersistRunner
BIN = EXP/"work"/"bin"; K = EXP/"kernels"

def build(kernel, fn="k"):
    out = HERE/(Path(kernel).stem+".bin")
    subprocess.run([str(BIN/"shdump"),"-o",str(out),"--no-fast-math",str(kernel),"-f",fn],
                   check=True, capture_output=True)
    buf = out.read_bytes()
    off, ln = agxparse.locate_region(buf,"_agc.main")
    _, pieces = agxparse.extract_agx(buf)
    return out, buf, off, pieces["_agc.main"]

def ints(raw): return [struct.unpack_from("<i",raw,i)[0] for i in range(0,len(raw)-3,4)]
def flts(raw): return [struct.unpack_from("<f",raw,i)[0] for i in range(0,len(raw)-3,4)]

# --- dsel5 -------------------------------------------------------------
arch, buf, roff, main = build(K/"dsel5.metal")
a = list(range(8))
(HERE/"a_int.bin").write_bytes(b"".join(struct.pack("<i",v) for v in a))
r = PersistRunner(source=str(K/"dsel5.metal"), function="k", fast_math=False,
                  agxrun_persist=str(BIN/"agxrun_persist"))
print("READY", r.device)
resp = r.request(archive=str(arch), grid=8, tg=8, ins={1:str(HERE/"a_int.bin")},
                 outs={0:32}, timeout=8)
print("dsel5 baseline", resp["status"], ints(resp["outs"].get(0,b"")),
      "expect", [(100 if x>5 else 200) for x in a])
r.close()

# --- gsel4 -------------------------------------------------------------
arch2, buf2, roff2, main2 = build(K/"gsel4.metal")
r = PersistRunner(source=str(K/"gsel4.metal"), function="k", fast_math=False,
                  agxrun_persist=str(BIN/"agxrun_persist"))
resp = r.request(archive=str(arch2), grid=8, tg=8, ins={1:str(HERE/"a_int.bin")},
                 outs={0:32}, timeout=8)
print("gsel4 baseline", resp["status"], ints(resp["outs"].get(0,b"")),
      "expect", [(111 if g<4 else 222) for g in range(8)])
r.close()
