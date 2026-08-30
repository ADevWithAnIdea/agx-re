// EXP-0161 authored probe kernels (G17P).
//
// Each kernel exists to make ONE instruction family appear in the compiled
// `_agc.main` of OUR OWN source, so a contiguous pure-ALU block containing it
// can be lifted byte-for-byte into a synthesized program (see
// harness/isa_helpers.py) or spliced in place in its natural anchor.
//
// Written by us for this experiment. Shapes (not results) follow the kernels
// EXP-0146 / EXP-0153 authored for the same instructions in this repository,
// so a G17P measurement is comparable with the M4 measurement it revisits.
//
// CLEAN-ROOM: our own MSL. No Apple source consulted; the only machine code
// this experiment inspects is what the PUBLIC runtime compiler produces from
// this file.
#include <metal_stdlib>
using namespace metal;

// ---- carry_gen ----------------------------------------------------------
// 64-bit unsigned add: provokes the iadd2(lo) -> carry_gen -> psel -> iadd2(hi)
// lowering chain (EXP-0038/EXP-0102/EXP-0146).
kernel void k_u64add(device const ulong *a  [[buffer(0)]],
                     device const ulong *b  [[buffer(1)]],
                     device ulong *out      [[buffer(2)]],
                     uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

// A second, independent carry_gen anchor: three-operand add, whose middle
// carry is the 0x22 sibling of the same byte+2==0x35 family.
kernel void k_u64add3(device const ulong *a  [[buffer(0)]],
                      device const ulong *b  [[buffer(1)]],
                      device ulong *out      [[buffer(2)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid] + (a[gid] ^ b[gid]);
}

// ---- mov_zext16 ---------------------------------------------------------
// The 16-bit zero-extend. Source is the immediately preceding load (this is
// the carrier in which EXP-0146 found byte+1 INERT).
kernel void k_zext16(device const uint *a [[buffer(0)]],
                     device uint *out     [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    out[gid] = uint(ushort(a[gid]));
}

// Two independent zero-extends of two different live values in one kernel.
kernel void k_zext16_two(device const uint *a [[buffer(0)]],
                         device const uint *b [[buffer(1)]],
                         device uint *out     [[buffer(2)]],
                         uint gid [[thread_position_in_grid]]) {
    uint x = a[gid];
    uint y = b[gid];
    out[gid] = uint(ushort(x)) + 65536u * uint(ushort(y));
}

// ---- ibfe ---------------------------------------------------------------
// Constant-offset / constant-width bitfield extract: EXP-0033's single-ibfe
// shape, the carrier EXP-0139 used for the offset/width rules.
kernel void k_bfe(device const uint *a [[buffer(0)]],
                  device uint *out     [[buffer(1)]],
                  uint gid [[thread_position_in_grid]]) {
    out[gid] = extract_bits(a[gid], 4u, 8u);
}

// A SECOND, independent ibfe lowering: the logical shift-right by a constant
// lowers to extract_bits(a, k, 32-k).
kernel void k_shr_const(device const uint *a [[buffer(0)]],
                        device uint *out     [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] >> 5u;
}

// ---- fspecial -----------------------------------------------------------
// `fast::` selects the single-op SFU datapath without turning fast-math on for
// the whole translation unit, so every other instruction in the probe keeps
// its ordinary lowering.
kernel void k_rsqrt(device const float *a [[buffer(0)]],
                    device float *out     [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = fast::rsqrt(a[gid]);
}

kernel void k_log2(device const float *a [[buffer(0)]],
                   device float *out     [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = fast::log2(a[gid]);
}

kernel void k_exp2(device const float *a [[buffer(0)]],
                   device float *out     [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = fast::exp2(a[gid]);
}

kernel void k_sqrt(device const float *a [[buffer(0)]],
                   device float *out     [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = fast::sqrt(a[gid]);
}

kernel void k_rcp(device const float *a [[buffer(0)]],
                  device float *out     [[buffer(1)]],
                  uint gid [[thread_position_in_grid]]) {
    out[gid] = 1.0f / a[gid];
}

kernel void k_floor(device const float *a [[buffer(0)]],
                    device float *out     [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = floor(a[gid]);
}

// The PRECISE reciprocal/root lowerings, which use the low-precision
// `fspecial_est` seed op rather than the single-op SFU.
kernel void k_rsqrt_precise(device const float *a [[buffer(0)]],
                            device float *out     [[buffer(1)]],
                            uint gid [[thread_position_in_grid]]) {
    out[gid] = precise::rsqrt(a[gid]);
}
