#!/usr/bin/env python3
# gen_kernels.py -- EXP-0033 integer/bitfield completeness provocation kernels.
# Each kernel is minimal so the compiler emits the target op (few instructions).
# CLEAN-ROOM: all of these are OUR OWN MSL.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
KD = os.path.join(HERE, "kernels")
os.makedirs(KD, exist_ok=True)

HDR = "#include <metal_stdlib>\nusing namespace metal;\n\n"

def w(name, body):
    with open(os.path.join(KD, f"{name}.metal"), "w") as f:
        f.write(HDR + body)

# ---- generic unary: out[gid] = f(a[gid]) ----
def unary(ty, oty, expr):
    return (f"kernel void k(device const {ty} *a [[buffer(0)]],\n"
            f"              device {oty} *out [[buffer(1)]],\n"
            f"              uint gid [[thread_position_in_grid]]) {{\n"
            f"    out[gid] = {expr};\n}}\n")

# ---- generic binary: out[gid] = f(a[gid], b[gid]) ----
def binary(ty, oty, expr):
    return (f"kernel void k(device const {ty} *a [[buffer(0)]],\n"
            f"              device const {ty} *b [[buffer(1)]],\n"
            f"              device {oty} *out [[buffer(2)]],\n"
            f"              uint gid [[thread_position_in_grid]]) {{\n"
            f"    out[gid] = {expr};\n}}\n")

# ---- generic ternary: out[gid] = f(a,b,c) ----
def ternary(ty, oty, expr):
    return (f"kernel void k(device const {ty} *a [[buffer(0)]],\n"
            f"              device const {ty} *b [[buffer(1)]],\n"
            f"              device const {ty} *c [[buffer(2)]],\n"
            f"              device {oty} *out [[buffer(3)]],\n"
            f"              uint gid [[thread_position_in_grid]]) {{\n"
            f"    out[gid] = {expr};\n}}\n")

# ================= Task 1: bit-count / bit-scan =================
w("popcnt_u",  unary("uint", "uint", "popcount(a[gid])"))
w("popcnt_i",  unary("int",  "int",  "popcount(a[gid])"))
w("clz_u",     unary("uint", "uint", "clz(a[gid])"))
w("clz_i",     unary("int",  "int",  "clz(a[gid])"))
w("ctz_u",     unary("uint", "uint", "ctz(a[gid])"))
w("ctz_i",     unary("int",  "int",  "ctz(a[gid])"))
w("revbits_u", unary("uint", "uint", "reverse_bits(a[gid])"))
w("revbits_i", unary("int",  "int",  "reverse_bits(a[gid])"))

# ================= Task 2: bitfield insert / extract =================
# unsigned extract (zero-extend) vs signed extract (sign-extend)
w("extr_u_imm", unary("uint", "uint", "extract_bits(a[gid], 4u, 8u)"))
w("extr_s_imm", unary("int",  "int",  "extract_bits(a[gid], 4u, 8u)"))
# variable offset/count extract
w("extr_u_var",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device const uint *off [[buffer(1)]],\n"
  "              device const uint *cnt [[buffer(2)]],\n"
  "              device uint *out [[buffer(3)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = extract_bits(a[gid], off[gid], cnt[gid]);\n}\n")
w("extr_s_var",
  "kernel void k(device const int *a [[buffer(0)]],\n"
  "              device const uint *off [[buffer(1)]],\n"
  "              device const uint *cnt [[buffer(2)]],\n"
  "              device int *out [[buffer(3)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = extract_bits(a[gid], off[gid], cnt[gid]);\n}\n")
# insert_bits (bitfield insert): base a, insert b, offset 3, count 5
w("insert_imm",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device const uint *b [[buffer(1)]],\n"
  "              device uint *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = insert_bits(a[gid], b[gid], 3u, 5u);\n}\n")
w("insert_var",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device const uint *b [[buffer(1)]],\n"
  "              device const uint *off [[buffer(2)]],\n"
  "              device const uint *cnt [[buffer(3)]],\n"
  "              device uint *out [[buffer(4)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = insert_bits(a[gid], b[gid], off[gid], cnt[gid]);\n}\n")

# ================= Task 3: rotate =================
w("rotl_var", binary("uint", "uint", "rotate(a[gid], b[gid])"))
w("rotl_imm", unary("uint", "uint", "rotate(a[gid], 5u)"))
# hand-written funnel/rotate lowering (does the compiler fuse to a rotate op?)
w("rotl_manual",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device const uint *n [[buffer(1)]],\n"
  "              device uint *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    uint x = a[gid]; uint s = n[gid] & 31u;\n"
  "    out[gid] = (x << s) | (x >> (32u - s));\n}\n")
# funnel shift across two words: metal has no direct funnel; hand-written
w("funnel_manual",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device const uint *b [[buffer(1)]],\n"
  "              device const uint *n [[buffer(2)]],\n"
  "              device uint *out [[buffer(3)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    uint s = n[gid] & 31u;\n"
  "    out[gid] = (a[gid] << s) | (b[gid] >> (32u - s));\n}\n")

# ================= Task 4: min3 / max3 / median3 / clamp =================
# direct built-ins (may not exist -> compile will fail; recorded as negative)
w("min3",   ternary("int",  "int",  "min3(a[gid], b[gid], c[gid])"))
w("max3",   ternary("int",  "int",  "max3(a[gid], b[gid], c[gid])"))
w("median3",ternary("int",  "int",  "median3(a[gid], b[gid], c[gid])"))
w("umin3",  ternary("uint", "uint", "min3(a[gid], b[gid], c[gid])"))
# nested fallbacks (always compile) for comparison
w("min3_nest",  ternary("int", "int", "min(min(a[gid], b[gid]), c[gid])"))
w("max3_nest",  ternary("int", "int", "max(max(a[gid], b[gid]), c[gid])"))
w("med3_nest",  ternary("int", "int", "max(min(a[gid], b[gid]), min(max(a[gid], b[gid]), c[gid]))"))
# clamp (integer)
w("clamp_i",   ternary("int",  "int",  "clamp(a[gid], b[gid], c[gid])"))
w("clamp_u",   ternary("uint", "uint", "clamp(a[gid], b[gid], c[gid])"))

# ================= Task 5: pack / unpack / as_type / 16-bit-packed =================
# as_type bitcast half2<->uint
w("astype_h2u", unary("uint", "uint",
  "as_type<uint>(as_type<half2>(a[gid]))"))   # round-trip u->h2->u (bitcast only)
w("astype_u2h",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device half2 *out [[buffer(1)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = as_type<half2>(a[gid]);\n}\n")
# pack/unpack unorm/snorm (fixed-function convert ops?)
w("pack_unorm2x16",
  "kernel void k(device const float2 *a [[buffer(0)]],\n"
  "              device uint *out [[buffer(1)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = pack_float_to_unorm2x16(a[gid]);\n}\n")
w("unpack_unorm2x16",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device float2 *out [[buffer(1)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = unpack_unorm2x16_to_float(a[gid]);\n}\n")
# native-half packed 2-lane ALU (0x10/0x11 groups)
w("half2_add",
  "kernel void k(device const half2 *a [[buffer(0)]],\n"
  "              device const half2 *b [[buffer(1)]],\n"
  "              device half2 *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n")
w("half2_mul",
  "kernel void k(device const half2 *a [[buffer(0)]],\n"
  "              device const half2 *b [[buffer(1)]],\n"
  "              device half2 *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] * b[gid];\n}\n")
w("half_add",
  "kernel void k(device const half *a [[buffer(0)]],\n"
  "              device const half *b [[buffer(1)]],\n"
  "              device half *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n")
# native-16-bit integer packed ops (short2 / ushort2)
w("short2_add",
  "kernel void k(device const short2 *a [[buffer(0)]],\n"
  "              device const short2 *b [[buffer(1)]],\n"
  "              device short2 *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n")
w("ushort_add",
  "kernel void k(device const ushort *a [[buffer(0)]],\n"
  "              device const ushort *b [[buffer(1)]],\n"
  "              device ushort *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n")

# ================= Task 6: 64-bit integer =================
# inputs/outputs are ulong/long -> handled as 2x uint32 words in the harness.
w("u64_add",
  "kernel void k(device const ulong *a [[buffer(0)]],\n"
  "              device const ulong *b [[buffer(1)]],\n"
  "              device ulong *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n")
w("u64_sub",
  "kernel void k(device const ulong *a [[buffer(0)]],\n"
  "              device const ulong *b [[buffer(1)]],\n"
  "              device ulong *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] - b[gid];\n}\n")
w("u64_mul",
  "kernel void k(device const ulong *a [[buffer(0)]],\n"
  "              device const ulong *b [[buffer(1)]],\n"
  "              device ulong *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] * b[gid];\n}\n")
w("u64_shl",
  "kernel void k(device const ulong *a [[buffer(0)]],\n"
  "              device const uint *n [[buffer(1)]],\n"
  "              device ulong *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] << n[gid];\n}\n")
w("u64_shr",
  "kernel void k(device const ulong *a [[buffer(0)]],\n"
  "              device const uint *n [[buffer(1)]],\n"
  "              device ulong *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] >> n[gid];\n}\n")
w("s64_cmp",
  "kernel void k(device const long *a [[buffer(0)]],\n"
  "              device const long *b [[buffer(1)]],\n"
  "              device int *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = (a[gid] < b[gid]) ? 1 : 0;\n}\n")
w("u64_cmp",
  "kernel void k(device const ulong *a [[buffer(0)]],\n"
  "              device const ulong *b [[buffer(1)]],\n"
  "              device int *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = (a[gid] < b[gid]) ? 1 : 0;\n}\n")
w("u64_from32",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device const uint *b [[buffer(1)]],\n"
  "              device ulong *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = (ulong)a[gid] * (ulong)b[gid];\n}\n")   # 32x32->64 widening mul
w("u64_popcnt",
  "kernel void k(device const ulong *a [[buffer(0)]],\n"
  "              device uint *out [[buffer(1)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = popcount(a[gid]);\n}\n")

names = sorted(os.listdir(KD))
print(f"wrote {len(names)} kernels to {KD}:")
for n in names:
    print("  ", n)
