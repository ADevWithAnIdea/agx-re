#!/usr/bin/env python3
# EXP-M4-11 item 2b (reproduces RT-7 t2b): the 0x09 32-bit falu2 size bit reads the LOW half.
# add kernel out=a+b. srcA=r2 (buffer1=b), srcB=r0 (buffer0=a). Put raw bits 0x00003C00 in b
# (float32 ~= 2.15e-41 ~= 0; low halfword 0x3C00 = half 1.0). srcB=a=100.
# 32-bit srcA: out = ~0 + 100 = 100. Splice srcA size bit (byte+1 bit0, file off 0x21) 1->0
# (16-bit): srcA reads the LOW halfword = half(0x3C00)=1.0 => out = 1.0 + 100 = 101.
import subprocess, os, struct
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
ROOT = _REPO; AGXTEST = os.path.join(ROOT, "tools/agxtest/agxtest.py")
SRC = "/private/tmp/claude-501/-Users-user-cleanroom-gpu/2b10ccd4-6b22-4ef0-899b-1cb5a544bbb2/scratchpad/mm/add.metal"
SRCA_OFF = 0x21
bval = struct.unpack('<f', bytes([0x00, 0x3C, 0x00, 0x00]))[0]   # raw 0x00003C00
print("b raw = 0x%08x  float=%g  (low half 0x3C00 = half 1.0)" % (0x00003C00, bval))

def run(splice=None):
    cmd = ["python3", AGXTEST, "--source", SRC, "--function", "k", "--grid", "4", "--tg", "4",
           "--buf", "0=100,100,100,100", "--buf", "1=%r,%r,%r,%r" % (bval, bval, bval, bval),
           "--out", "2=4", "--run-timeout", "25"]
    if splice: cmd += ["--splice", splice]
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = [float(x) for x in line.split()[2:]]
    return st, res

print("32-bit srcA (baseline): expect ~100 ->", run())
print("16-bit srcA (size bit 0x21:0x05->0x04): expect 101 ->",
      run("_agc.main@0x%x=04" % SRCA_OFF))
