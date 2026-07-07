#!/usr/bin/env python3
# EXP-0020 -- register-pressure kernel generator + dumper (runs ON DEVICE).
# Generates compute kernels that hold K simultaneously-live 32-bit values via a
# cyclic FMA chain across a data-dependent loop (so the allocator cannot collapse
# them), compiles each with shdump, extracts _agc.main, and prints a per-K line:
#   K  MAINLEN  NINSTR  NMEM(0x67/0xe7)  MAXREG  HEX
# CLEAN-ROOM: only our own MSL is compiled, only our own bytes inspected.
import os, subprocess, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("agxparse", os.path.join(HERE, "agxparse.py"))
agxparse = importlib.util.module_from_spec(spec); spec.loader.exec_module(agxparse)

def kernel_src(K, dtype="float"):
    # K live accumulators, cyclic cross-dependency, data-dependent trip count.
    lines = []
    lines.append("#include <metal_stdlib>")
    lines.append("using namespace metal;")
    lines.append("kernel void k(device %s* out [[buffer(0)]]," % dtype)
    lines.append("              device const %s* in [[buffer(1)]]," % dtype)
    lines.append("              constant uint& n [[buffer(2)]],")
    lines.append("              uint gid [[thread_position_in_grid]]) {")
    for k in range(K):
        lines.append("  %s a%d = in[gid*%d+%d];" % (dtype, k, K, k))
    lines.append("  for (uint i=1;i<n;i++) {")
    lines.append("    %s t = in[i];" % dtype)
    for k in range(K):
        lines.append("    a%d = fma(a%d, t, a%d);" % (k, k, (k+1) % K))
    lines.append("  }")
    for k in range(K):
        lines.append("  out[gid*%d+%d] = a%d;" % (K, k, k))
    lines.append("}")
    return "\n".join(lines) + "\n"

def dump(K, dtype="float"):
    src = kernel_src(K, dtype)
    kp = os.path.join(HERE, "kernels", "p%s%d.metal" % (dtype[0], K))
    with open(kp, "w") as f: f.write(src)
    arch = os.path.join(HERE, "k_%s%d.bin" % (dtype[0], K))
    cmd = [os.path.join(HERE, "shdump"), "-o", arch, "-f", "k", "--no-fast-math", kp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(arch):
        return "K=%d COMPILE_FAIL %s" % (K, r.stderr[-200:])
    with open(arch, "rb") as f: buf = f.read()
    _, pieces = agxparse.extract_agx(buf)
    main = pieces.get("_agc.main") if pieces else None
    if main is None:
        return "K=%d EXTRACT_FAIL" % K
    os.remove(arch)
    return "K=%d %s LEN=%d" % (K, dtype, len(main)), main.hex()

if __name__ == "__main__":
    dtype = sys.argv[1] if len(sys.argv) > 1 else "float"
    Ks = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else \
         [2,4,8,12,16,24,32,40,48,56,60,62,64,66,68,72,80,96,112,128,160,200,256]
    for K in Ks:
        res = dump(K, dtype)
        if isinstance(res, tuple):
            hdr, hexs = res
            print(hdr)
            print("HEX", hexs)
        else:
            print(res)
        sys.stdout.flush()
