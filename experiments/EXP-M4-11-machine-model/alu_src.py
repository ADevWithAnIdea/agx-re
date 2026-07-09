#!/usr/bin/env python3
# EXP-M4-11 item 1c: ALU-source out-of-file reads 0 (no fault) + no mod-64 aliasing (r64!=r0).
# Kernel out=a+b; falu2 fadd @0x20, srcB_reg = byte+3 (file off 0x23), enc (reg<<1)|size.
# Baseline srcB=r0 holds b -> out=a+b. Splice srcB to another register:
#   r64/r96 are UNINITIALIZED (read 0) IF distinct from r0 -> out=a (b-term drops to 0).
#   If the field were mod-64, r64 would ALIAS r0 -> still read b -> out=a+b (unchanged).
# So out==a after r64-splice proves r64 != r0 (no mod-64 alias); r96 out==a & STATUS OK
# proves out-of-file ALU source reads 0 (no fault). CLEAN-ROOM: own MSL/own bytes.
import subprocess, os
# --- portable repo root (repo was relocated; anchor to a sentinel, not a hardcoded path) ---
import os
def _repo_root(start):
    d = os.path.abspath(start)
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')) and os.path.isdir(os.path.join(d, 'tools', 'agx-isa')):
            return d
        d = os.path.dirname(d)
    raise RuntimeError('repo root not found from ' + start)
_REPO = _repo_root(os.path.dirname(os.path.abspath(__file__)))
# --- end portable repo root ---
ROOT = _REPO
AGXTEST = os.path.join(ROOT, "tools/agxtest/agxtest.py")
SRC = "/private/tmp/claude-501/-Users-user-cleanroom-gpu/2b10ccd4-6b22-4ef0-899b-1cb5a544bbb2/scratchpad/mm/add.metal"
SRCB_OFF = 0x23
A = [1, 2, 3, 4, 5, 6, 7, 8]
B = [10, 20, 30, 40, 50, 60, 70, 80]

def run(byteval=None):
    cmd = ["python3", AGXTEST, "--source", SRC, "--function", "k", "--grid", "8", "--tg", "8",
           "--buf", "0=" + ",".join(map(str, A)), "--buf", "1=" + ",".join(map(str, B)),
           "--out", "2=8", "--run-timeout", "25"]
    if byteval is not None:
        cmd += ["--splice", "_agc.main@0x%x=%02x" % (SRCB_OFF, byteval)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = [round(float(x)) for x in line.split()[2:]]
    return st, res

print("baseline srcB=r0 (holds b): expect a+b =", [a + b for a, b in zip(A, B)])
print("  ", run())
apb = [a + b for a, b in zip(A, B)]
for reg in [0, 32, 64, 96, 127]:
    bv = (reg << 1) | 1
    st, res = run(bv)
    if res == A: interp = "reads 0  -> out=a (register EMPTY/out-of-file, != r0)"
    elif res == apb: interp = "reads b  -> ALIASES r0 (mod-64!) or unchanged"
    else: interp = "other"
    print("  srcB=r%-3d byte0x%02x: STATUS=%-12s out=%s  %s" % (reg, bv, st, res, interp))
