#!/usr/bin/env python3
# EXP-M4-11 item 1c (7-bit srcA path, as RT-7 used): out-of-file reads 0, r64 distinct from r0.
# add kernel out=a+b; falu2 @0x20. srcA_reg = byte+1 (file off 0x21), 7-bit (reg<<1)|size.
# In this compile srcA=r2 holds b, srcB=r0 holds a  =>  out = srcA + a.
#   srcA=r0 (a) -> a+a=[2,4,..]; srcA=r2 (b) -> a+b=[11,22,..] (baseline)
#   srcA=rN empty (reads 0) -> 0+a = a = [1,2,..8]
# If splicing srcA->r64 yields a (=[1..8]) it read 0 (r64 is a DISTINCT empty register,
# not truncated to r0 which would give [2,4,..]) => r64 != r0, 7-bit field reaches r64.
# srcA->r96 yielding a with STATUS OK => out-of-file ALU source reads 0, no fault.
import subprocess, os
ROOT = "/Users/user/cleanroom_gpu"
AGXTEST = os.path.join(ROOT, "tools/agxtest/agxtest.py")
SRC = "/private/tmp/claude-501/-Users-user-cleanroom-gpu/2b10ccd4-6b22-4ef0-899b-1cb5a544bbb2/scratchpad/mm/add.metal"
SRCA_OFF = 0x21
A = [1, 2, 3, 4, 5, 6, 7, 8]; B = [10, 20, 30, 40, 50, 60, 70, 80]

def run(byteval=None):
    cmd = ["python3", AGXTEST, "--source", SRC, "--function", "k", "--grid", "8", "--tg", "8",
           "--buf", "0=" + ",".join(map(str, A)), "--buf", "1=" + ",".join(map(str, B)),
           "--out", "2=8", "--run-timeout", "25"]
    if byteval is not None:
        cmd += ["--splice", "_agc.main@0x%x=%02x" % (SRCA_OFF, byteval)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = [round(float(x)) for x in line.split()[2:]]
    return st, res

aa = [2 * a for a in A]; apb = [a + b for a, b in zip(A, B)]
print("baseline srcA=r2(b): out=a+b=", apb, "->", run())
print("legend: out=a[1..8]=>srcA read 0 (empty reg); out=[2,4..]=>srcA aliases r0(=a); out=[11,22..]=>reads b")
for reg in [0, 2, 32, 63, 64, 66, 95, 96, 127]:
    bv = (reg << 1) | 1
    st, res = run(bv)
    if res == A: interp = "reads 0  (DISTINCT empty reg)"
    elif res == aa: interp = "= r0 value (a) -> ALIASES r0"
    elif res == apb: interp = "reads b (=r2, baseline)"
    else: interp = "other"
    print("  srcA=r%-3d byte0x%02x: STATUS=%-12s out=%s  %s" % (reg, bv, st, res, interp))
