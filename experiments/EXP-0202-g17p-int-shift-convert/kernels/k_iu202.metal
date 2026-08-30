// EXP-0202 `iunary` candidate carriers (AUTHORED BY US; OWN-SHADER).
//
// TARGET FIELDS: `iunary.b1` (byte+1) and `iunary.opsel` (byte+2). NO RAW EXISTS
// FOR EITHER -- neither has ever been dispatched on any target.
//
// `iunary` is the LOOSE byte0 == 0x27 catch-all: whatever is left of that opcode
// space once the tight `ibitcount` descriptor (byte+2 == 0x56, 15 match bits) has
// taken the popcount/find-msb/reverse member. db.json's `opsel` enum names the
// datapaths -- 0x56 int-unary/convert, 0x22 rt/interp, 0x10 convert, 0x26
// convert2, 0x07 logic -- and its provenance note says the residue instances were
// found via byte+1 == 0x2d.
//
// We cannot ask for an opcode; we can only write MSL and see what the compiler
// reaches for. This file is therefore a NET, not a hypothesis: ~20 short unary /
// convert / bit-manipulation kernels spanning integer unary ops, width converts,
// float<->int converts, bit-casts, packing/unpacking and saturating arithmetic.
// `analysis/census.py` tokenizes every one with the PINNED db and keeps only
// occurrences the tokenizer calls `iunary` (NOT `ibitcount`); arms are built from
// those and from nothing else. A kernel that yields no `iunary` is dropped before
// the freeze and the drop is recorded -- that is data about which datapaths our
// own MSL can reach, which is itself the answer to "what can an emitter provoke".
//
// ORACLE: every expected value is computed on the host from the same inputs by
// the same arithmetic. Inputs:
//   a[t] = {15, 16, 65535, 0x40000001, 0x7FFFFFFF, 0xFFFFFFFF, 3, 0x80000000}
//   f[t] = {3.9, -3.9, 2.5, -2.5, 100.75, 7.0, 0.5, 63.25}
//
// SENTINEL out[8] = 12345, written first. POISON on buffer 0.
// CLEAN-ROOM: our own MSL. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

#define SENT out[8] = 12345u;

kernel void k_iu_ctz(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT out[t] = ctz(a[t]) + 1u;
}
kernel void k_iu_absi(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT out[t] = uint(abs(int(a[t]))) + 1u;
}
kernel void k_iu_sexth(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT out[t] = uint(int(short(a[t]))) ^ 5u;
}
kernel void k_iu_sextb(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT out[t] = uint(int(char(a[t]))) ^ 5u;
}
kernel void k_iu_zextb(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT out[t] = uint(uchar(a[t])) + 5u;
}
kernel void k_iu_i2f(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT out[t] = as_type<uint>(float(int(a[t])) * 0.5f);
}
kernel void k_iu_u2f(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT out[t] = as_type<uint>(float(a[t]) * 0.25f);
}
kernel void k_iu_f2h(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT out[t] = uint(as_type<ushort>(half(f[t] * 3.0f))) + 1u;
}
kernel void k_iu_h2f(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT half h = half(f[t]); out[t] = as_type<uint>(float(h) + 1.5f);
}
kernel void k_iu_h2i(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT half h = half(f[t] * 4.0f); out[t] = uint(int(h)) ^ 7u;
}
kernel void k_iu_bitcast(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                         uint t [[thread_position_in_grid]]) {
    SENT out[t] = as_type<uint>(f[t]) ^ 0x55u;
}
kernel void k_iu_unorm(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT float4 v = unpack_unorm4x8_to_float(a[t]); out[t] = as_type<uint>(v.x + v.y * 2.0f + v.z * 4.0f + v.w * 8.0f);
}
kernel void k_iu_packun(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                        uint t [[thread_position_in_grid]]) {
    SENT float4 v = float4(f[t] * 0.01f, 0.25f, 0.5f, 0.75f); out[t] = pack_float_to_unorm4x8(v) + 1u;
}
kernel void k_iu_packsn(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                        uint t [[thread_position_in_grid]]) {
    SENT float4 v = float4(f[t] * 0.01f, -0.25f, 0.5f, -0.75f); out[t] = pack_float_to_snorm4x8(v) + 1u;
}
kernel void k_iu_unpsn(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT float4 v = unpack_snorm4x8_to_float(a[t]); out[t] = as_type<uint>(v.x * 3.0f + v.w);
}
kernel void k_iu_addsat(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                        device const uint *b [[buffer(2)]], uint t [[thread_position_in_grid]]) {
    SENT out[t] = addsat(a[t], b[t]) ^ 1u;
}
kernel void k_iu_subsat(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                        device const uint *b [[buffer(2)]], uint t [[thread_position_in_grid]]) {
    SENT out[t] = subsat(a[t], b[t]) ^ 1u;
}
kernel void k_iu_sat(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT out[t] = as_type<uint>(saturate(f[t] * 0.1f) + 0.125f);
}
kernel void k_iu_rint(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT out[t] = as_type<uint>(rint(f[t]) + 0.5f);
}
kernel void k_iu_trunc(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT out[t] = as_type<uint>(trunc(f[t]) + 0.5f);
}
kernel void k_iu_h2u(device uint *out [[buffer(0)]], device const float *f [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT half h = half(fabs(f[t]) * 8.0f); out[t] = uint(ushort(h)) + 3u;
}
kernel void k_iu_ushort2f(device uint *out [[buffer(0)]], device const uint *a [[buffer(1)]],
                          uint t [[thread_position_in_grid]]) {
    SENT out[t] = as_type<uint>(float(ushort(a[t])) * 0.5f + 0.25f);
}
