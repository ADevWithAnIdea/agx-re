#!/usr/bin/env python3
# EXP-M5-21 -- (a) uniform-register-file footprint ladder, (b) max GPR index the compiler
# emits in a high-pressure kernel (via the M5 tokenizer). COMPILE-ONLY.
# CLEAN-ROOM: OWN-SHADER. Only our own MSL compiled; only our own bytes/metadata inspected.
import os, sys, subprocess, struct, importlib.util, re

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.expanduser("~/cleanroom_work/tools")
SHDUMP = os.path.join(TOOLS, "shdump", "shdump")
spec = importlib.util.spec_from_file_location("ap", os.path.join(TOOLS, "shdump", "agxparse.py"))
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
# M5 tokenizer
sys.path.insert(0, os.path.join(TOOLS, "agx-isa-m5"))
import importlib.util as ilu
isaspec = ilu.spec_from_file_location("agxisa_m5", os.path.join(TOOLS, "agx-isa-m5", "agxisa.py"))
AMP = chr(38)

def gpu(buf):
    for off, size, note in ap.iter_gpu_images(buf):
        try: mo = ap.MachO(buf, off)
        except ValueError: continue
        if mo.cputype == ap.APPLE_GPU_CPUTYPE: return mo

def table_fields(buf, tpos):
    soff = struct.unpack_from('<i', buf, tpos)[0]; vt = tpos - soff
    nf = (struct.unpack_from('<H', buf, vt)[0] - 4) // 2; f = {}
    for i in range(nf):
        fo = struct.unpack_from('<H', buf, vt + 4 + i * 2)[0]
        if fo: f[i] = tpos + fo
    return f

def all_fields(buf, mo):
    s = mo.find_section("__TEXT", "__compute"); nb = mo.base + s["offset"]; nm = ap.MachO(buf, nb)
    meta = None
    for sec in nm.sections:
        if sec["seg"] == "__GPU_METADATA":
            o = nb + sec["offset"]; meta = bytes(buf[o:o + sec["size"]])
    if meta is None: return {}
    root = struct.unpack_from('<I', meta, 0)[0]; rf = table_fields(meta, root)
    if 0 not in rf: return {}
    sub = rf[0] + struct.unpack_from('<I', meta, rf[0])[0]; ff = table_fields(meta, sub)
    return {i: (struct.unpack_from('<I', meta, p)[0] if p + 4 <= len(meta) else meta[p]) for i, p in ff.items()}

def compile_src(src, name):
    kp = os.path.join(HERE, "kernels", name + ".metal"); open(kp, "w").write(src)
    arch = os.path.join(HERE, name + ".bin")
    subprocess.run([SHDUMP, "-o", arch, "-f", "k", "--no-fast-math", kp], capture_output=True)
    if not os.path.exists(arch): return None, None
    buf = open(arch, "rb").read(); mo = gpu(buf)
    _, pieces = ap.extract_agx(buf); main = pieces["_agc.main"]
    fields = all_fields(buf, mo); os.remove(arch)
    return main, fields

def uniform_kernel(n):
    L = ["#include <metal_stdlib>", "using namespace metal;",
         "kernel void k(device int* out [[buffer(0)]],"]
    for i in range(n): L.append("  constant int%s u%d [[buffer(%d)]]," % (AMP, i, i + 1))
    L.append("  uint gid [[thread_position_in_grid]]) {")
    L.append("  out[gid] = " + "+".join("u%d" % i for i in range(n)) + "; }")
    return "\n".join(L) + "\n"

def press_kernel(K):
    L = ["#include <metal_stdlib>", "using namespace metal;",
         "kernel void k(device int* out [[buffer(0)]], device const int* in [[buffer(1)]],",
         "              constant uint%s n [[buffer(2)]], uint gid [[thread_position_in_grid]]) {" % AMP]
    for k in range(K): L.append("  int a%d = in[gid*%d+%d];" % (k, K, k))
    L.append("  for (uint i=1;i<n;i++) { int t=in[i];")
    for k in range(K): L.append("    a%d = a%d*t + a%d;" % (k, k, (k + 1) % K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d] = a%d;" % (K, k, k))
    L.append("}")
    return "\n".join(L) + "\n"

def maxreg_from_tokens(main):
    # tokenize with M5 DB, collect every rNN mentioned, return max index
    mod = ilu.module_from_spec(isaspec)
    try:
        isaspec.loader.exec_module(mod)
    except Exception as e:
        return None, "tokenizer-load-fail:%s" % e
    hexs = main.hex()
    try:
        toks = mod.tokenize(bytes.fromhex(hexs)) if hasattr(mod, "tokenize") else None
    except Exception:
        toks = None
    # fall back: run the agxisa.py CLI tokenizer
    return None, "cli"

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "uniform"
    if mode == "uniform":
        print("# uniform footprint ladder")
        for n in [1, 2, 4, 8, 16, 32, 48, 64, 96, 128, 160, 192, 224, 256]:
            main, fields = compile_src(uniform_kernel(n), "u%d" % n)
            if main is None: print("n=%d COMPILE_FAIL" % n); continue
            small = {i: v for i, v in sorted(fields.items()) if v < 20000}
            print("n=%-4d mainlen=%-4d fields=%s" % (n, len(main), small))
            sys.stdout.flush()
    elif mode == "maxreg":
        K = int(sys.argv[2]) if len(sys.argv) > 2 else 96
        main, fields = compile_src(press_kernel(K), "mr%d" % K)
        print("K=%d f0=%s mainlen=%d" % (K, fields.get(0), len(main)))
        # write hex for external tokenization
        open(os.path.join(HERE, "raw", "press_K%d.hex" % K), "w").write(main.hex())
        print("HEX_WRITTEN raw/press_K%d.hex" % K)
