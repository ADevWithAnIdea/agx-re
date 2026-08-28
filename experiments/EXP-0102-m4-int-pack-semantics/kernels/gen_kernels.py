#!/usr/bin/env python3
# gen_kernels.py -- EXP-0102 INT-*/PACK-* provocation kernels. All OUR OWN MSL.
# Runtime-variable (buffer-fed) operands are used wherever a boundary/masking
# claim is under test, so the compiler cannot constant-fold the interesting
# case away; compile-time immediates are used only where the ITEM itself asks
# about the immediate-operand encoding (INT-04).
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HDR = "#include <metal_stdlib>\nusing namespace metal;\n\n"


def w(fname, body):
    with open(os.path.join(HERE, fname), "w") as f:
        f.write(HDR + body)
    print("wrote", fname)


# ===================== INT-01 / INT-02 / INT-03: bitfield extract =====================
w("k_int_extract.metal",
  "kernel void extru(device const uint *a [[buffer(0)]],\n"
  "                   device const uint *off [[buffer(1)]],\n"
  "                   device const uint *cnt [[buffer(2)]],\n"
  "                   device uint *out [[buffer(3)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = extract_bits(a[gid], off[gid], cnt[gid]);\n"
  "}\n\n"
  "kernel void extrs(device const int *a [[buffer(0)]],\n"
  "                   device const uint *off [[buffer(1)]],\n"
  "                   device const uint *cnt [[buffer(2)]],\n"
  "                   device int *out [[buffer(3)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = extract_bits(a[gid], off[gid], cnt[gid]);\n"
  "}\n")

# ===================== INT-11: bitfield insert =====================
w("k_int_insert.metal",
  "kernel void ins(device const uint *base [[buffer(0)]],\n"
  "                 device const uint *val [[buffer(1)]],\n"
  "                 device const uint *off [[buffer(2)]],\n"
  "                 device const uint *cnt [[buffer(3)]],\n"
  "                 device uint *out [[buffer(4)]],\n"
  "                 uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = insert_bits(base[gid], val[gid], off[gid], cnt[gid]);\n"
  "}\n")

# ===================== INT-04: rotate by IMMEDIATE (compile-time const) ============
for K in (0, 1, 31, 32, 33, 63, 64):
    w(f"k_int_rotate_imm{K}.metal",
      "kernel void k(device const uint *a [[buffer(0)]],\n"
      "              device uint *out [[buffer(1)]],\n"
      "              uint gid [[thread_position_in_grid]]) {\n"
      f"    out[gid] = rotate(a[gid], {K}u);\n}}\n")

# ===================== INT-05 / INT-06: rotate by RUNTIME amount ===================
w("k_int_rotate_var.metal",
  "kernel void k(device const uint *a [[buffer(0)]],\n"
  "              device const uint *n [[buffer(1)]],\n"
  "              device uint *out [[buffer(2)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = rotate(a[gid], n[gid]);\n}\n")

# ===================== INT-07 / INT-08: IMAD wrap + register pressure ==============
w("k_int_imad.metal",
  "kernel void imadu(device const uint *a [[buffer(0)]],\n"
  "                   device const uint *b [[buffer(1)]],\n"
  "                   device const uint *c [[buffer(2)]],\n"
  "                   device uint *out [[buffer(3)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] * b[gid] + c[gid];\n}\n\n"
  "kernel void imads(device const int *a [[buffer(0)]],\n"
  "                   device const int *b [[buffer(1)]],\n"
  "                   device const int *c [[buffer(2)]],\n"
  "                   device int *out [[buffer(3)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] * b[gid] + c[gid];\n}\n")

# Register-pressure IMAD: many independent live temporaries computed from a
# wide input array, all kept live until the final mad, to try to force the
# allocator past the low registers the other kernels naturally use.
pressure_lines = []
for i in range(40):
    pressure_lines.append(f"    uint t{i} = in[{i}] ^ (in[{i}] << {(i % 13) + 1}) + gid;")
sum_expr = " + ".join(f"t{i}" for i in range(40))
w("k_int_imad_pressure.metal",
  "kernel void k(device const uint *in [[buffer(0)]],\n"
  "              device const uint *mb [[buffer(1)]],\n"
  "              device const uint *mc [[buffer(2)]],\n"
  "              device uint *out [[buffer(3)]],\n"
  "              uint gid [[thread_position_in_grid]]) {\n"
  + "\n".join(pressure_lines) + "\n"
  f"    uint acc = ({sum_expr});\n"
  "    out[gid] = acc * mb[gid] + mc[gid];\n"
  "}\n")

# ===================== INT-09 / INT-10: clz + popcount baseline ====================
w("k_int_clz.metal",
  "kernel void clzu(device const uint *a [[buffer(0)]],\n"
  "                  device uint *out [[buffer(1)]],\n"
  "                  uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = clz(a[gid]);\n}\n\n"
  "kernel void popc(device const uint *a [[buffer(0)]],\n"
  "                  device uint *out [[buffer(1)]],\n"
  "                  uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = popcount(a[gid]);\n}\n")

# ===================== INT-12: 16 two-input Boolean logic functions ================
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
import oracle as O  # noqa: E402

logic_fns = []
for idx in range(16):
    expr = O.LOGIC_EXPR[idx]
    logic_fns.append(
        f"kernel void k{idx}(device const uint *a [[buffer(0)]],\n"
        f"                device const uint *b [[buffer(1)]],\n"
        f"                device uint *out [[buffer(2)]],\n"
        f"                uint gid [[thread_position_in_grid]]) {{\n"
        f"    uint a_ = a[gid]; uint b_ = b[gid];\n"
        f"    out[gid] = {expr.replace('a','a_').replace('b','b_')};\n}}\n")
w("k_int_logic16.metal", "\n".join(logic_fns))

# ===================== INT-13 / INT-14: u64 carry-generate =========================
w("k_int_u64carry.metal",
  "kernel void u64add(device const ulong *a [[buffer(0)]],\n"
  "                    device const ulong *b [[buffer(1)]],\n"
  "                    device ulong *out [[buffer(2)]],\n"
  "                    uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n\n"
  "kernel void u64add_expr(device const ulong *a [[buffer(0)]],\n"
  "                         device const ulong *b [[buffer(1)]],\n"
  "                         device const ulong *c [[buffer(2)]],\n"
  "                         device ulong *out [[buffer(3)]],\n"
  "                         uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = (a[gid] + b[gid]) + c[gid];\n}\n")

# ===================== PACK-01 / PACK-02: pack_half_2x16 equivalent ================
w("k_pack_half2x16.metal",
  "kernel void packh(device const float2 *a [[buffer(0)]],\n"
  "                   device uint *out [[buffer(1)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    half2 h = half2(a[gid]);\n"
  "    out[gid] = as_type<uint>(h);\n}\n\n"
  "kernel void unpackh(device const uint *a [[buffer(0)]],\n"
  "                     device float2 *out [[buffer(1)]],\n"
  "                     uint gid [[thread_position_in_grid]]) {\n"
  "    half2 h = as_type<half2>(a[gid]);\n"
  "    out[gid] = float2(h);\n}\n")

# ===================== PACK-03 / PACK-04: snorm2x16 =====================
w("k_pack_snorm2x16.metal",
  "kernel void packsn(device const float2 *a [[buffer(0)]],\n"
  "                    device uint *out [[buffer(1)]],\n"
  "                    uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = pack_float_to_snorm2x16(a[gid]);\n}\n\n"
  "kernel void unpacksn(device const uint *a [[buffer(0)]],\n"
  "                      device float2 *out [[buffer(1)]],\n"
  "                      uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = unpack_snorm2x16_to_float(a[gid]);\n}\n")

# ===================== PACK-05 / PACK-06: unorm2x16 =====================
w("k_pack_unorm2x16.metal",
  "kernel void packun(device const float2 *a [[buffer(0)]],\n"
  "                    device uint *out [[buffer(1)]],\n"
  "                    uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = pack_float_to_unorm2x16(a[gid]);\n}\n\n"
  "kernel void unpackun(device const uint *a [[buffer(0)]],\n"
  "                      device float2 *out [[buffer(1)]],\n"
  "                      uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = unpack_unorm2x16_to_float(a[gid]);\n}\n")

# Exhaustive 16-bit-lane unpack: gid IS the 16-bit pattern, packed into both
# lanes (u = gid | (gid<<16)); only the low-lane (x) result is stored, so
# every one of the 65536 possible 16-bit lane patterns is exercised exactly
# once, in ONE dispatch.
w("k_pack_unpack_exhaustive.metal",
  "kernel void unpacksn_exh(device float *out [[buffer(0)]],\n"
  "                          uint gid [[thread_position_in_grid]]) {\n"
  "    uint u = gid | (gid << 16);\n"
  "    out[gid] = unpack_snorm2x16_to_float(u).x;\n}\n\n"
  "kernel void unpackun_exh(device float *out [[buffer(0)]],\n"
  "                          uint gid [[thread_position_in_grid]]) {\n"
  "    uint u = gid | (gid << 16);\n"
  "    out[gid] = unpack_unorm2x16_to_float(u).x;\n}\n")

# ===================== PACK-07 / PACK-08: 4x8 pack/unpack =====================
w("k_pack_4x8_unorm.metal",
  "kernel void packu4x8(device const float4 *a [[buffer(0)]],\n"
  "                      device uint *out [[buffer(1)]],\n"
  "                      uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = pack_float_to_unorm4x8(a[gid]);\n}\n\n"
  "kernel void unpacku4x8(device const uint *a [[buffer(0)]],\n"
  "                        device float4 *out [[buffer(1)]],\n"
  "                        uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = unpack_unorm4x8_to_float(a[gid]);\n}\n")

w("k_pack_4x8_snorm.metal",
  "kernel void packs4x8(device const float4 *a [[buffer(0)]],\n"
  "                      device uint *out [[buffer(1)]],\n"
  "                      uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = pack_float_to_snorm4x8(a[gid]);\n}\n\n"
  "kernel void unpacks4x8(device const uint *a [[buffer(0)]],\n"
  "                        device float4 *out [[buffer(1)]],\n"
  "                        uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = unpack_snorm4x8_to_float(a[gid]);\n}\n")

# Hand-written GENERIC (non-normalized) 4-lane 8-bit integer pack idiom --
# probes whether a plain integer 4x8 gather has native support beyond the
# float-normalized pack_*_4x8 builtins.
w("k_pack_4x8_manual.metal",
  "kernel void packu4x8_manual(device const uint *a [[buffer(0)]],\n"
  "                             device const uint *b [[buffer(1)]],\n"
  "                             device const uint *c [[buffer(2)]],\n"
  "                             device const uint *d [[buffer(3)]],\n"
  "                             device uint *out [[buffer(4)]],\n"
  "                             uint gid [[thread_position_in_grid]]) {\n"
  "    uint r = (a[gid] & 0xFFu) | ((b[gid] & 0xFFu) << 8) |\n"
  "             ((c[gid] & 0xFFu) << 16) | ((d[gid] & 0xFFu) << 24);\n"
  "    out[gid] = r;\n}\n")

# ===================== PACK-09 / PACK-10: half2 exceptional-value matrix ===========
w("k_pack_half2_alu.metal",
  "kernel void h2add(device const half2 *a [[buffer(0)]],\n"
  "                   device const half2 *b [[buffer(1)]],\n"
  "                   device half2 *out [[buffer(2)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n\n"
  "kernel void h2mul(device const half2 *a [[buffer(0)]],\n"
  "                   device const half2 *b [[buffer(1)]],\n"
  "                   device half2 *out [[buffer(2)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] * b[gid];\n}\n\n"
  "kernel void h2fma(device const half2 *a [[buffer(0)]],\n"
  "                   device const half2 *b [[buffer(1)]],\n"
  "                   device const half2 *c [[buffer(2)]],\n"
  "                   device half2 *out [[buffer(3)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = fma(a[gid], b[gid], c[gid]);\n}\n")

# ===================== PACK-11: short2 int16 packed ALU (negative claim) ===========
w("k_pack_short2.metal",
  "kernel void s2add(device const short2 *a [[buffer(0)]],\n"
  "                   device const short2 *b [[buffer(1)]],\n"
  "                   device short2 *out [[buffer(2)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] + b[gid];\n}\n\n"
  "kernel void s2mul(device const short2 *a [[buffer(0)]],\n"
  "                   device const short2 *b [[buffer(1)]],\n"
  "                   device short2 *out [[buffer(2)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] * b[gid];\n}\n\n"
  "kernel void s2and(device const short2 *a [[buffer(0)]],\n"
  "                   device const short2 *b [[buffer(1)]],\n"
  "                   device short2 *out [[buffer(2)]],\n"
  "                   uint gid [[thread_position_in_grid]]) {\n"
  "    out[gid] = a[gid] & b[gid];\n}\n")

print("done")
