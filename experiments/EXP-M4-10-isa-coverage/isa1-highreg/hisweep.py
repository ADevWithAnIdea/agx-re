#!/usr/bin/env python3
# ISA-1 high-register operand sweep (float fadd path via hiadd staging movs).
# Splices one source-operand byte in _agc.main to select register N ((reg<<1)|size)
# and RUNS on the local Apple9 GPU, reading out[0]=content(rN)+const. Derives the
# physical-register->value map, proving the operand encoding. CLEAN-ROOM: own MSL only.
import subprocess, sys, os, struct

ROOT = "/Users/user/cleanroom_gpu"
AGXTEST = os.path.join(ROOT, "tools/agxtest/agxtest.py")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "kernels/hiadd.metal")
NFILE = os.path.join(HERE, "work/n1.bin")
os.makedirs(os.path.join(HERE, "work"), exist_ok=True)
open(NFILE, "wb").write(struct.pack("<I", 1))  # uint n = 1 (loop no-op)

INVALS = [1000 + k for k in range(96)]

def run(splice_off, byteval):
    cmd = ["python3", AGXTEST, "--source", SRC, "--function", "k",
           "--grid", "1", "--tg", "1",
           "--buf", "1=" + ",".join(str(x) for x in INVALS),
           "--buf", f"2=@{NFILE}",
           "--out", "0=1"]
    if byteval is not None:
        cmd += ["--splice", f"_agc.main@0x{splice_off:x}={byteval:02x}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    status = None; res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): status = line.split()[1]
        if line.startswith("RESULT"): res = line.split()[2:]
    val = None
    if res:
        try: val = float(res[0])
        except: val = res[0]
    return status, val

def sweep(name, off):
    print(f"\n### {name}  (splice _agc.main@0x{off:x})  [baseline byte in kernel]")
    st, base = run(off, None)
    print(f"  baseline (no splice): STATUS={st} out0={base}")
    regs = [0, 1, 15, 16, 31, 32, 63, 64, 65, 79, 95]
    print("  reg | (reg<<1)|1 read32 | (reg<<1)|0 read16")
    rows = {}
    for N in regs:
        st1, v1 = run(off, (N << 1) | 1)
        st0, v0 = run(off, (N << 1) | 0)
        rows[N] = (v1, v0)
        print(f"  r{N:<3d} 0x{(N<<1)|1:02x}->{str(v1):>14s} [{st1}]   0x{(N<<1)|0:02x}->{str(v0):>14s} [{st0}]")
    return base, rows

if __name__ == "__main__":
    # mov1 feeds a[68] (baseline src byte 0x8a=r69). mov2 feeds a[69] (0x8c=r70).
    sweep("mov1 (a[68] operand)", 0x0989)
    sweep("mov2 (a[69] operand)", 0x0991)
