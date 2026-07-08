#!/usr/bin/env python3
# Splice byte+12 (op selector) of the add-baseline atomic (abs offset 0x38 in
# _agc.main) to each candidate op-code and record the HW result. Two input sets:
#   arith : INITIAL=12, V0=10  (distinguishes add/sub/and/or/xor + min/max)
#   sign  : INITIAL=1,  V0=-1  (0xFFFFFFFF; straddles sign boundary -> smin/smax
#           differ from umin/umax)
# Only OUR OWN compiled add.metal bytes are spliced. Result read back from buf0.
import os, subprocess, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
AGXTEST = os.path.join(ROOT, "tools", "agxtest", "agxtest.py")
SRC = os.path.join(HERE, "kernels", "add.metal")
W = os.path.join(HERE, "work")
OFF = 0x38  # byte+12 of the atomic at +0x2c

CODES = [
    ("add",   0x20), ("sub", 0x36), ("and", 0x22), ("or", 0x2c),
    ("xor",   0x3e), ("smax", 0x28), ("smin", 0x2a), ("umax", 0x38),
    ("umin",  0x3a), ("fadd", 0x26), ("xchg", 0x3c), ("cmpxchg", 0x24),
]

def run(initial, v0, code):
    splice = f"_agc.main@{OFF:#x}={code:02x}"
    cmd = ["python3", AGXTEST, "--source", SRC, "--function", "k",
           "--grid", "1", "--tg", "1", "--int",
           "--buf", f"0={initial}", "--buf", f"1={v0}", "--out", "0=1",
           "--splice", splice, "--workdir", W, "--run-timeout", "20"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    status = "?"; result = None; outhex = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS "): status = line.split(None,1)[1]
        elif line.startswith("RESULT 0"): result = line.split(None,2)[2]
        elif line.startswith("OUT 0"): outhex = line.split(None,2)[2]
    return status, result, outhex

def as_signed(h):
    if h is None: return None
    b = bytes.fromhex(h)[:4]
    return struct.unpack("<i", b)[0]

def as_unsigned(h):
    if h is None: return None
    b = bytes.fromhex(h)[:4]
    return struct.unpack("<I", b)[0]

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "arith"
    if which == "arith":
        initial, v0 = 12, 10
    elif which == "sign":
        initial, v0 = 1, -1
    elif which == "float":
        # INITIAL=2.0f bits, V0=1.0f bits, all as int
        initial, v0 = 0x40000000, 0x3F800000
    else:
        initial, v0 = int(sys.argv[1]), int(sys.argv[2])
    print(f"# input set '{which}': INITIAL={initial} (0x{initial & 0xffffffff:08x}), "
          f"V0={v0} (0x{v0 & 0xffffffff:08x})")
    print(f"{'op':8} {'code':4} {'status':10} {'result_i':12} {'result_u':12} {'rawhex'}")
    for name, code in CODES:
        st, res, outh = run(initial, v0, code)
        si = as_signed(outh); ui = as_unsigned(outh)
        print(f"{name:8} 0x{code:02x} {st:10} {str(si):12} {str(ui):12} {outh}")
