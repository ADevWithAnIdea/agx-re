#!/usr/bin/env python3
# RT-1a-FIX item 2: INDEPENDENT HW re-validation of iadd2 add/sub polarity.
# Claim (RT-1a): the compiler emits byte0 0x9f for a plain ADD and 0x1f for a
# SUBTRACT. The DB's canonical iadd2 matches [0:7]==0x1f with srcA_neg=0 and
# semantics d=srcA+srcB -- but on HW 0x1f (srcA_neg=0) SUBTRACTS and 0x9f
# (srcA_neg=1) ADDS. So the DB's srcA_neg polarity + semantics are inverted.
#
# Method: iaddbank.metal computes out[gid]=p.x+p.y (a CLEAN exposed iadd2 at
# main+0x34, byte0=0x9f). Feed p.x=10,p.y=20 -> expect 30 unspliced. Splice
# byte0 0x9f->0x1f and read back: if it becomes 10-20=-10 (=4294967286 as u32),
# then 0x9f=ADD, 0x1f=SUBTRACT (RT-1a correct). Also splice 0x1f->0x9f on a real
# subtract for the symmetric check.
import sys, os, subprocess, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

ARCH = "iaddbank.bin"
MAIN_OFF = int(subprocess.check_output(
    ["python3", "agxparse.py", ARCH, "--locate", "_agc.main"], text=True).split()[0])
base = open(ARCH, "rb").read()
INSN_OFF = 0x34
assert base[MAIN_OFF + INSN_OFF] == 0x9f, "expected 0x9f add at +0x34"

# v = int4 p (v[0..3]), int4 q (v[4..7]); grid=1 gid=0
open("v.bin", "wb").write(struct.pack("<8i", 10, 20, 30, 40, 1, 2, 3, 4))
ins = {3: "v.bin"}
outs = {0: 4}

r = PersistRunner(source="rt1a_iaddbank.metal", function="k", fast_math=False,
                  agxrun_persist="./agxrun_persist")
def run(b0):
    sp = bytearray(base); sp[MAIN_OFF + INSN_OFF] = b0
    open("sp.bin", "wb").write(sp)
    resp = r.request(archive="sp.bin", grid=1, tg=1, ins=ins, outs=outs, timeout=6)
    if resp["status"] != "OK":
        return resp["status"], None
    o0 = struct.unpack("<i", resp["outs"][0])[0]
    return "OK", o0
try:
    print("# p.x=10 p.y=20 ; out=p.x+p.y")
    for b0 in (0x9f, 0x1f):
        st, v = run(b0)
        interp = "ADD (10+20=30)" if v == 30 else ("SUBTRACT (10-20=-10)" if v == -10 else "?")
        print(f"  byte0=0x{b0:02x} -> {st} out={v}  => {interp}")
finally:
    r.close()
