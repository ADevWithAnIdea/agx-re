#!/usr/bin/env python3
# EXP-M4-11 item 7 (reproduces EXP-0025): async completion = HW register interlock, no software
# scoreboard. Three observations:
#  (A) pointer-chase: 8 dependent index loads (each feeds the next index) -> correct chained result
#      is produced with NO explicit wait/scoreboard op in the compiled code (the consumer op
#      directly follows the load) => the RAW hazard is enforced by a HW register interlock.
#  (B) 20 INDEPENDENT loads sum correctly => >8 in flight, i.e. no G13-style AGX_MAX_PENDING=8 cap.
#  (C) tokenize both kernels and confirm NO 'wait'/scoreboard instruction exists (G17P/Apple9 ISA).
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
ISA = os.path.join(ROOT, "tools/agx-isa/agxisa.py")
HERE = os.path.dirname(os.path.abspath(__file__)); K = os.path.join(HERE, "kernels")

CHASE = """#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]], device const uint* idx [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    uint i = gid;
    for (uint s=0; s<8; ++s) i = idx[i];   // each load's result indexes the next load (RAW chain)
    out[gid] = i;
}
"""
SUM20 = """#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    uint s = 0;
    for (int j=0; j<20; ++j) s += a[gid + j*37];   // 20 INDEPENDENT loads, no inter-dependency
    out[gid] = s;
}
"""

def compile_run(name, src, nbuf, buf1, grid, out_n, dump=False):
    kp = os.path.join(K, name + ".metal"); open(kp, "w").write(src)
    cmd = ["python3", AGXTEST, "--source", kp, "--function", "k", "--grid", str(grid), "--tg",
           str(min(grid, 64)), "--int", "--buf", "1=" + ",".join(map(str, buf1)),
           "--out", "0=%d" % out_n, "--run-timeout", "25"]
    if dump: cmd.append("--dump-main")
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = main = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = [int(x) for x in line.split()[2:]]
        if line.startswith("MAIN_ORIG"): main = line.split()[1]
    return st, res, main

# (A) pointer chase: idx[i]=(i+1)%N, chase 8 -> out[gid]=(gid+8)%N
N = 64
idx = [(i + 1) % N for i in range(N)]
st, res, main = compile_run("chase", CHASE, 2, idx, 16, 16, dump=True)
exp = [(g + 8) % N for g in range(16)]
print("(A) pointer-chase (8 dependent loads): STATUS=%s" % st)
print("    out    =", res)
print("    expect =", exp, "->", "CORRECT (interlock enforced)" if res == exp else "WRONG")
tok = subprocess.run(["python3", ISA, "tokenize", main], capture_output=True, text=True).stdout
nload = tok.count("device_load")
waits = [l for l in tok.splitlines() if any(w in l.lower() for w in ("wait", "scoreboard", "sbwait"))]
print("    compiled: %d device_load ops; wait/scoreboard ops found = %d %s"
      % (nload, len(waits), waits if waits else "(none -> no software scoreboard)"))

# (B) 20 independent loads summed. a[i]=i -> out[gid]=sum_{j}(gid+37j)
M = 16 + 20 * 37
a = list(range(M))
st, res, main2 = compile_run("sum20", SUM20, 2, a, 16, 16, dump=True)
exp2 = [sum((g + 37 * j) for j in range(20)) for g in range(16)]
print("\n(B) 20 independent loads summed: STATUS=%s" % st)
print("    match=%s (out[0]=%s exp[0]=%s)" % (res == exp2, res[0] if res else None, exp2[0]))
tok2 = subprocess.run(["python3", ISA, "tokenize", main2], capture_output=True, text=True).stdout
print("    compiled device_load ops =", tok2.count("device_load"),
      "; wait/scoreboard ops =", sum(1 for l in tok2.splitlines()
                                     if any(w in l.lower() for w in ("wait", "scoreboard"))))
