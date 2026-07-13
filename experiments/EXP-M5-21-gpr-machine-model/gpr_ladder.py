#!/usr/bin/env python3
# EXP-M5-21 -- M5 (G17g) GPR machine-model ladder (COMPILE-ONLY + optional HW copy check).
#
# Compiles a ladder of own-MSL kernels holding K simultaneously-live 32-bit (float or int)
# or 16-bit (half) values via a cyclic FMA chain across a data-dependent loop (so the
# allocator cannot collapse them). For each K it:
#   * extracts _agc.main (our own compiled bytes),
#   * parses OUR OWN archive's __GPU_METADATA FlatBuffer and dumps *every* small stat field
#     (so we CONFIRM which field is GPR/scratch/uniform on G17g, not assume the A18 index),
#   * (int only, --run) runs the kernel with n=1 so the loop degenerates to a K-register
#     copy out[k]=in[k], exact-comparing the output => proves the K values survived on HW.
#
# CLEAN-ROOM: OWN-SHADER. Only our own MSL is compiled; only our own compiled bytes and our
# own archive's own self-describing metadata FlatBuffer are inspected (parsed with our own
# parser). No Apple binary disassembled/introspected.
import os, sys, subprocess, struct, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.expanduser("~/cleanroom_work/tools")
SHDUMP = os.path.join(TOOLS, "shdump", "shdump")
AGXRUN = os.path.join(TOOLS, "agxtest", "agxrun")
spec = importlib.util.spec_from_file_location("ap", os.path.join(TOOLS, "shdump", "agxparse.py"))
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def kernel_src(K, dtype):
    L = ["#include <metal_stdlib>", "using namespace metal;",
         "kernel void k(device %s* out [[buffer(0)]]," % dtype,
         "              device const %s* in [[buffer(1)]]," % dtype,
         "              constant uint& n [[buffer(2)]],",
         "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  %s a%d = in[gid*%d+%d];" % (dtype, k, K, k))
    L.append("  for (uint i=1;i<n;i++) {")
    L.append("    %s t = in[i];" % dtype)
    for k in range(K): L.append("    a%d = a%d*t + a%d;" % (k, k, (k+1) % K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d] = a%d;" % (K, k, k))
    L.append("}")
    return "\n".join(L) + "\n"

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

def all_stat_fields(buf, mo):
    s = mo.find_section("__TEXT", "__compute"); nb = mo.base + s["offset"]; nm = ap.MachO(buf, nb)
    meta = None
    for sec in nm.sections:
        if sec["seg"] == "__GPU_METADATA":
            o = nb + sec["offset"]; meta = bytes(buf[o:o + sec["size"]])
    if meta is None: return None, {}
    root = struct.unpack_from('<I', meta, 0)[0]; rf = table_fields(meta, root)
    if 0 not in rf: return len(meta), {}
    sub = rf[0] + struct.unpack_from('<I', meta, rf[0])[0]; ff = table_fields(meta, sub)
    out = {}
    for i, p in ff.items():
        out[i] = struct.unpack_from('<I', meta, p)[0] if p + 4 <= len(meta) else meta[p]
    return len(meta), out

def build(K, dtype):
    src = kernel_src(K, dtype)
    kp = os.path.join(HERE, "kernels", "p%s%d.metal" % (dtype[0], K))
    open(kp, "w").write(src)
    arch = os.path.join(HERE, "arch_%s%d.bin" % (dtype[0], K))
    subprocess.run([SHDUMP, "-o", arch, "-f", "k", "--no-fast-math", kp], capture_output=True)
    return kp, arch

def run_copy(kp, arch, K, dtype):
    # n=1 => loop no-op => out==in. int/float exact compare.
    inbuf = os.path.join(HERE, "in.bin"); nbuf = os.path.join(HERE, "n.bin")
    if dtype == "int":
        vals = list(range(1, K + 1)); pk = "<i"
    elif dtype == "float":
        vals = [float(v) for v in range(1, K + 1)]; pk = "<f"
    else:  # half: skip HW compare (half readback nontrivial)
        return "skip", None
    open(inbuf, "wb").write(b"".join(struct.pack(pk, v) for v in vals))
    open(nbuf, "wb").write(struct.pack("<I", 1))
    try:
        r = subprocess.run([AGXRUN, "--archive", arch, "--source", kp, "--function", "k",
                            "--no-fast-math", "--grid", "1", "--tg", "1",
                            "--buf", "1=%s" % inbuf, "--buf", "2=%s" % nbuf,
                            "--out", "0=%d" % (K * 4)],
                           capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", None
    status = "?"; got = None
    for ln in r.stdout.splitlines():
        if ln.startswith("STATUS "): status = ln.split()[1]
        if ln.startswith("OUT 0 "):
            bb = bytes.fromhex(ln.split(None, 2)[2])
            got = [struct.unpack_from(pk, bb, j)[0] for j in range(0, len(bb), 4)]
    return status, (got == vals)

if __name__ == "__main__":
    dtype = "float"; do_run = False; Ks = None
    args = sys.argv[1:]
    rest = []
    for a in args:
        if a == "--run": do_run = True
        elif a in ("float", "int", "half"): dtype = a
        else: rest.append(a)
    if rest: Ks = [int(x) for x in rest]
    if Ks is None:
        Ks = [2, 4, 8, 12, 16, 24, 32, 40, 48, 56, 64, 72, 76, 80, 84, 88, 92, 96,
              100, 104, 112, 120, 128, 144, 160, 192, 224, 256]
    print("# dtype=%s run=%s" % (dtype, do_run))
    print("%-5s %-7s %-8s %s" % ("K", "MLEN", "allfields(idx:val, val<20000)", ""))
    for K in Ks:
        kp, arch = build(K, dtype)
        if not os.path.exists(arch):
            print("K=%-5d COMPILE_FAIL" % K); sys.stdout.flush(); continue
        buf = open(arch, "rb").read(); mo = gpu(buf)
        _, pieces = ap.extract_agx(buf); main = pieces["_agc.main"]
        mlen, fields = all_stat_fields(buf, mo)
        small = {i: v for i, v in sorted(fields.items()) if v < 20000}
        line = "K=%-4d mlen=%-4d fields=%s" % (K, mlen, small)
        if do_run and dtype in ("int", "float"):
            st, ok = run_copy(kp, arch, K, dtype)
            line += " | copy=%s(%s)" % ("PASS" if ok else "FAIL", st)
        print(line); sys.stdout.flush()
        os.remove(arch)
