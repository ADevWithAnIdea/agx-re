#!/usr/bin/env python3
# EXP-M4-11 item 1b: memory-index register hard boundary at r95/r96.
# Kernel out[gid]=in[gid]; the device_load(0x67) index_reg is byte+5 (file off 0x09).
# Splice byte+5 to select which GPR feeds the array index. For r0..r95 the register is
# in-file (uninitialized ones read 0 -> a[0]); r96+ should HARD-FAULT (CMDBUF_ERROR) as
# an out-of-file index register. A clean r95->r96 fault edge + no aliasing = 96 is a hard
# silicon boundary, not mod-64. CLEAN-ROOM: own MSL, own compiled bytes.
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
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "kernels/cp.metal")
IDX_OFF = 0x09  # device_load @0x04, byte+5
INVALS = [100 + i for i in range(8)]

def run(byteval):
    cmd = ["python3", AGXTEST, "--source", SRC, "--function", "k", "--grid", "8", "--tg", "8",
           "--int", "--buf", "1=" + ",".join(str(x) for x in INVALS), "--out", "0=8",
           "--splice", "_agc.main@0x%x=%02x" % (IDX_OFF, byteval), "--run-timeout", "25"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = line.split()[2:]
    return st, res

print("baseline (unspliced byte+5=0x01 reads gid):")
b = subprocess.run(["python3", AGXTEST, "--source", SRC, "--function", "k", "--grid", "8", "--tg", "8",
                    "--int", "--buf", "1=" + ",".join(str(x) for x in INVALS), "--out", "0=8",
                    "--run-timeout", "25"], capture_output=True, text=True)
for l in b.stdout.splitlines():
    if l.startswith(("STATUS", "RESULT")): print("  ", l)

print("\n-- sweep memory-index byte+5 (reg = byte & 0x7f) around 95/96 --")
for reg in [0, 1, 32, 63, 64, 94, 95, 96, 97, 100, 126, 127]:
    for flag in [0x00, 0x80]:   # bit7 = scalar/size flag; test both
        bv = (reg & 0x7f) | flag
        st, res = run(bv)
        allsame = res and len(set(res)) == 1
        note = ("all=%s" % res[0]) if allsame else ("out=%s" % res)
        print("  r%-3d flag%02x byte0x%02x: STATUS=%-12s %s" % (reg, flag, bv, st, note))
