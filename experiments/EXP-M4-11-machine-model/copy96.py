#!/usr/bin/env python3
# EXP-M4-11 item 1 (functional no-alias proof, reproduces RT-7): a cyclic-FMA kernel with
# K live accumulators forces the allocator to reserve up to 96 DISTINCT GPRs (f0). The trip
# count is runtime-1 (compiler can't fold it), so the loop body never runs and the kernel is
# a pure per-thread copy out[k]=in[k]. If the 96 allocated GPRs aliased mod-64 (r64==r0),
# a_k and a_(k+64) would share a physical reg and the copy would corrupt. Exact copy of all
# K values with f0 near 96 and scratch=0 => 96 distinct registers, no aliasing.
# CLEAN-ROOM: own MSL only.
import os, subprocess, struct, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(HERE, "harness")
ROOT = "/Users/user/cleanroom_gpu"; AGXTEST = os.path.join(ROOT, "tools/agxtest/agxtest.py")
spec = importlib.util.spec_from_file_location("ap", os.path.join(H, "agxparse.py"))
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
from meta_sweep import gpu, meta_regfields  # reuse metadata parser

def src(K):
    L = ["#include <metal_stdlib>", "using namespace metal;",
         "kernel void k(device float* out [[buffer(0)]],",
         "              device const float* in [[buffer(1)]],",
         "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  float a%d = in[gid*%d+%d];" % (k, K, k))
    L.append("  uint n = (gid > 0x7fffffffu) ? 64u : 1u;")  # runtime==1, unfoldable
    L.append("  for (uint i=1;i<n;i++) {")
    L.append("    float t = in[i];")
    for k in range(K): L.append("    a%d = fma(a%d, t, a%d);" % (k, k, (k + 1) % K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d] = a%d;" % (K, k, k))
    L.append("}")
    return "\n".join(L) + "\n"

def footprint(kp):
    arch = os.path.join(HERE, "work", "cp_probe.bin")
    subprocess.run([os.path.join(H, "shdump"), "-o", arch, "-f", "k", "--no-fast-math", kp],
                   capture_output=True)
    buf = open(arch, "rb").read(); mo = gpu(buf)
    s = mo.find_section("__TEXT", "__compute"); nb = mo.base + s["offset"]; nm = ap.MachO(buf, nb)
    meta = b""
    for sec in nm.sections:
        if sec["seg"] == "__GPU_METADATA":
            o = nb + sec["offset"]; meta = bytes(buf[o:o + sec["size"]])
    os.remove(arch); rf = meta_regfields(meta)
    return rf.get(0, (0, 0))[1], rf.get(41, rf.get(14, (0, 0)))[1]

for K in [60, 62, 66, 70, 72]:
    kp = os.path.join(HERE, "kernels", "cp%d.metal" % K)
    open(kp, "w").write(src(K))
    f0, scr = footprint(kp)
    invals = [float(1000 + i) for i in range(K)]   # distinct values 1000..1000+K-1
    cmd = ["python3", AGXTEST, "--source", kp, "--function", "k", "--grid", "1", "--tg", "1",
           "--buf", "1=" + ",".join("%g" % v for v in invals), "--out", "0=%d" % K,
           "--run-timeout", "25"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = [round(float(x)) for x in line.split()[2:]]
    ok = res == [int(v) for v in invals]
    print("K=%-3d f0=%-3d scratch=%-4d STATUS=%-10s copy_exact=%s%s"
          % (K, f0, scr, st, ok, "" if ok else "  GOT=%s" % res))
