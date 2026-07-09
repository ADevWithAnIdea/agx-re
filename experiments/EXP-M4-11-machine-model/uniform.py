#!/usr/bin/env python3
# EXP-M4-11 item 3: uniform register file + BOTH uniform-source encodings (reproduces RT-7 §3).
# uniB.metal (a+p.k) -> falu2_uni (uniform as srcA), select bit39 = byte+4 bit7.
# uniA.metal (p.k+a) -> falu2     (uniform as srcB), select = byte+2 bit4 + byte+5 bit1.
# Both falu2 at file offset 0x12. Tests: (1) out tracks the RUNTIME bound uniform (7/55/1000);
# (2) splicing the select bit makes the operand read the GPR (=0) instead -> out = a.
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
ROOT = _REPO; AGXTEST = os.path.join(ROOT, "tools/agxtest/agxtest.py")
HERE = os.path.dirname(os.path.abspath(__file__))
A = [10, 20, 30, 40, 50, 60, 70, 80]

def run(src, kval, splice=None):
    cmd = ["python3", AGXTEST, "--source", os.path.join(HERE, "kernels", src), "--function", "k",
           "--grid", "8", "--tg", "8", "--buf", "1=" + ",".join(map(str, A)),
           "--buf", "2=%g" % kval, "--out", "0=8", "--run-timeout", "25"]
    if splice: cmd += ["--splice", splice]
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = [round(float(x)) for x in line.split()[2:]]
    return st, res

print("== runtime-uniform read (out should = a + k) ==")
for src, tag in [("uniB.metal", "srcA-form falu2_uni"), ("uniA.metal", "srcB-form falu2")]:
    print(" %s (%s):" % (src, tag))
    for k in [7, 55, 1000]:
        st, res = run(src, k)
        exp = [a + k for a in A]
        print("   k=%-5d out=%s  %s" % (k, res, "OK track" if res == exp else "MISMATCH exp %s" % exp))

print("\n== splice select bit -> operand reads GPR (=0), out should become a =", A, "==")
# srcA-form (uniB): bit39 = byte+4 bit7; falu2_uni@0x12 -> byte+4 = 0x16 (0x80 -> 0x00)
st, res = run("uniB.metal", 7, "_agc.main@0x16=00")
print(" srcA-form clear bit39 (0x16:0x80->0x00): out=%s  %s" % (res, "GPR read (=0)" if res == A else "??"))
# srcB-form (uniA): byte+5 bit1; falu2@0x12 -> byte+5 = 0x17 (0xc2 -> 0xc0, clear bit1)
st, res = run("uniA.metal", 7, "_agc.main@0x17=c0")
print(" srcB-form clear byte+5 bit1 (0x17:0xc2->0xc0): out=%s  %s" % (res, "GPR read (=0)" if res == A else "??"))
# srcB-form alt toggle: byte+2 bit4; falu2@0x12 -> byte+2 = 0x14 (0x0c -> 0x1c, set bit4)
st, res = run("uniA.metal", 7, "_agc.main@0x14=1c")
print(" srcB-form set byte+2 bit4 (0x14:0x0c->0x1c):   out=%s  %s" % (res, "GPR read (=0)" if res == A else "??"))
