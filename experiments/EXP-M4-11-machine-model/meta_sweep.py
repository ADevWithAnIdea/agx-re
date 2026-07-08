#!/usr/bin/env python3
# EXP-M4-11 item 1a/2a/4a: register-footprint + scratch sweep from our own shader's
# own __GPU_METADATA FlatBuffer (OWN-SHADER). Generates cyclic-FMA kernels holding K
# simultaneously-live 32-bit (or 16-bit half) values, compiles each with our shdump,
# and reads:
#   field 0  = GPR footprint (regs)   field 14/41 = scratch bytes (spill)
# Confirms: f0 caps at exactly 96 (32-bit), ~50 for 64 halves, scratch>0 above 96.
# CLEAN-ROOM: only our own MSL compiled; only our own bytes/metadata inspected.
import os, sys, subprocess, struct, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
H = os.path.join(HERE, "harness")
spec = importlib.util.spec_from_file_location("ap", os.path.join(H, "agxparse.py"))
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def gpu(buf):
    for off, size, note in ap.iter_gpu_images(buf):
        try: mo = ap.MachO(buf, off)
        except ValueError: continue
        if mo.cputype == ap.APPLE_GPU_CPUTYPE: return mo

def kernel_src(K, dtype="float"):
    L = ["#include <metal_stdlib>", "using namespace metal;",
         "kernel void k(device %s* out [[buffer(0)]]," % dtype,
         "              device const %s* in [[buffer(1)]]," % dtype,
         "              constant uint& n [[buffer(2)]],",
         "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  %s a%d = in[gid*%d+%d];" % (dtype, k, K, k))
    L.append("  for (uint i=1;i<n;i++) {")
    L.append("    %s t = in[i];" % dtype)
    for k in range(K): L.append("    a%d = fma(a%d, t, a%d);" % (k, k, (k+1) % K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d] = a%d;" % (K, k, k))
    L.append("}")
    return "\n".join(L) + "\n"

def table_fields(buf, tpos):
    soff = struct.unpack_from('<i', buf, tpos)[0]; vt = tpos - soff
    vtsize = struct.unpack_from('<H', buf, vt)[0]; nf = (vtsize - 4) // 2
    fields = {}
    for i in range(nf):
        foff = struct.unpack_from('<H', buf, vt + 4 + i * 2)[0]
        if foff: fields[i] = tpos + foff
    return fields

def meta_regfields(meta):
    root = struct.unpack_from('<I', meta, 0)[0]
    rf = table_fields(meta, root)
    if 0 not in rf: return {}
    f0pos = rf[0]; sub = f0pos + struct.unpack_from('<I', meta, f0pos)[0]
    ff = table_fields(meta, sub)
    return {i: (p, struct.unpack_from('<I', meta, p)[0] if p + 4 <= len(meta) else meta[p]) for i, p in ff.items()}

def measure(K, dtype):
    src = kernel_src(K, dtype)
    kp = os.path.join(HERE, "kernels", "p%s%d.metal" % (dtype[0], K))
    os.makedirs(os.path.join(HERE, "kernels"), exist_ok=True)
    open(kp, "w").write(src)
    arch = os.path.join(HERE, "work", "fb_%s%d.bin" % (dtype[0], K))
    os.makedirs(os.path.join(HERE, "work"), exist_ok=True)
    r = subprocess.run([os.path.join(H, "shdump"), "-o", arch, "-f", "k", "--no-fast-math", kp],
                       capture_output=True, text=True)
    if not os.path.exists(arch): return None
    buf = open(arch, "rb").read(); mo = gpu(buf)
    s = mo.find_section("__TEXT", "__compute"); nb = mo.base + s["offset"]; nm = ap.MachO(buf, nb)
    meta = b""
    for sec in nm.sections:
        if sec["seg"] == "__GPU_METADATA":
            o = nb + sec["offset"]; meta = bytes(buf[o:o + sec["size"]])
    os.remove(arch)
    rf = meta_regfields(meta)
    f0 = rf.get(0, (0, 0))[1]
    scratch = rf.get(41, rf.get(14, (0, 0)))[1]
    return f0, scratch, rf

if __name__ == "__main__":
    dtype = sys.argv[1] if len(sys.argv) > 1 else "float"
    if dtype == "float":
        Ks = [2,4,8,16,32,48,60,62,64,66,68,72,80,88,92,93,96,100,104,112,128,160,192,256]
    else:
        Ks = [2,4,8,16,32,48,60,64,72,80,96,112,128]
    print("%-5s %-8s %-10s %s" % ("K", "f0(regs)", "scratchB", "smallfields"))
    for K in Ks:
        m = measure(K, dtype)
        if m is None: print("K=%d COMPILE_FAIL" % K); continue
        f0, scratch, rf = m
        small = {i: v for i, (p, v) in sorted(rf.items()) if i not in (0,) and v < 4096}
        print("%-5d %-8d %-10d %s" % (K, f0, scratch, small))
        sys.stdout.flush()
