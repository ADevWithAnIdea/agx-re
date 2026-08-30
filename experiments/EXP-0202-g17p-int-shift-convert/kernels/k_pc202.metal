// EXP-0202 bit-count carriers (AUTHORED BY US; OWN-SHADER).
//
// TARGET FIELDS: `ibitcount.cache` (bit 17 = byte+2 bit 1) and `ibitcount.dst`
// (bits 24..31).
//
// `cache` -- db.json calls it a writeback-enable and pairs 0x54 ("result consumed
// by a following ALU") against 0x56 ("standalone, writes back"). The dimension is
// therefore RESULT ROUTING, and EXP-0169's one carrier was a standalone popcount
// stored straight to memory: one point in it. The set below spans the dimension:
//
//   k_pc_store  popcount -> device store            (standalone)
//   k_pc_alu    popcount -> multiply/add -> store   (consumed by an ALU op)
//   k_pc_cmp    popcount -> compare -> select       (consumed by a compare)
//   k_pc_two    two popcounts summed                (consumed, two occurrences)
//   k_pc_tg     popcount -> THREADGROUP memory -> barrier -> store
//   k_pc_clz    find-msb form (fn_hi=1, form=5)
//   k_pc_rev    reverse-bits form (fn_hi=1, form=4)
//
// k_pc_tg exists because of a specific warning: `cache` fields in this corpus
// read inert because a single-pass, single-threadgroup carrier physically cannot
// express a memory/coherency dimension. It runs at grid=64, tg=32 -- multi-wave,
// multi-threadgroup -- and the count crosses threadgroup memory and a barrier
// before it is stored.
//
// `dst` -- db.json models it as reg<<1. PRE-REGISTERED PREDICTION: the following
// store still reads the COMPILED register, so the program reproduces the oracle
// iff value == compiled_dst and is broken for every other value. That is a
// two-class, per-value, host-computed oracle. (`iunary.dst`, the same byte,
// faults reproducibly at 192-241 and 243-255 on M4; the G17P behaviour of that
// region is a secondary pre-registered question.)
//
// ORACLE inputs (host-computed, no expected value is 0):
//   a[t] = {15, 16, 65535, 0x40000001, 0x7FFFFFFF, 0xFFFFFFFF, 3, 0x80000000}
//   b[t] = {1, 3, 7, 15, 31, 63, 127, 255}
// popcount(a) = [4,1,16,2,31,32,2,1] -- eight distinct-ish, all non-zero.
//
// SENTINEL out[8] = 12345 (out[64] in the threadgroup carrier), written first,
// through a device store independent of every instruction under test.
// POISON: buffer 0 pre-filled with 0xDEADBEEF+i by the harness.
//
// CLEAN-ROOM: our own MSL. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

#define SENT out[8] = 12345u;

kernel void k_pc_store(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = popcount(a[t]);
}

kernel void k_pc_alu(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = popcount(a[t]) * 3u + 7u;
}

kernel void k_pc_cmp(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = (popcount(a[t]) > 3u) ? (a[t] | 1u) : (b[t] | 2u);
}

kernel void k_pc_two(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = popcount(a[t]) + popcount(b[t]) * 64u;
}

kernel void k_pc_clz(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = clz(a[t]) + 1u;
}

kernel void k_pc_rev(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = reverse_bits(a[t]) ^ 5u;
}

// grid = 64, tg = 32: multi-wave, multi-threadgroup, and the count crosses
// threadgroup memory and a barrier before it reaches the device store.
kernel void k_pc_tg(device uint *out [[buffer(0)]],
                    device const uint *a [[buffer(1)]],
                    uint t [[thread_position_in_grid]],
                    uint l [[thread_position_in_threadgroup]]) {
    out[64] = 12345u;
    threadgroup uint sh[32];
    sh[l] = popcount(a[t & 7u]) + 1u;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[t] = sh[(l + 1u) & 31u] * 3u + 5u;
}
