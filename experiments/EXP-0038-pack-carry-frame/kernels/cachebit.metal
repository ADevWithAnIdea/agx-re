#include <metal_stdlib>
using namespace metal;

// ---- Task 4: 0x54 <-> 0x56 cache-bit variants (simd_reduce / unpack) ----
// Census flagged simd_reduce (bf 00 54 vs the named bf ..56) and unpack
// (17 04 54 vs 17 ..56) variants differing only in byte+2 bit1 (0x02).
// Provoke reductions where the source liveness differs to flip the bit.

// simd sum, result stored immediately (source is last-use).
kernel void k_reduce1(device const uint* a [[buffer(0)]],
                      device uint* out       [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = simd_sum(a[gid]);
}

// simd sum where the input value is ALSO stored (source NOT last-use).
kernel void k_reduce2(device const uint* a [[buffer(0)]],
                      device uint* out       [[buffer(1)]],
                      device uint* passthru  [[buffer(2)]],
                      uint gid [[thread_position_in_grid]]) {
    uint v = a[gid];
    passthru[gid] = v;          // v used again -> not last-use at the reduce
    out[gid] = simd_sum(v);
}

// two reductions of the same source (first is not last-use, second is).
kernel void k_reduce_two(device const uint* a [[buffer(0)]],
                         device uint* out       [[buffer(1)]],
                         uint gid [[thread_position_in_grid]]) {
    uint v = a[gid];
    uint s1 = simd_sum(v);
    uint s2 = simd_max(v);
    out[gid] = s1 + s2;
}

// prefix scan (exclusive) - different dtype/shape byte+7.
kernel void k_scan(device const uint* a [[buffer(0)]],
                   device uint* out       [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = simd_prefix_exclusive_sum(a[gid]);
}

// unpack in two contexts (last-use vs reused packed source).
kernel void k_unpack1(device const uint* a  [[buffer(0)]],
                      device float2* out     [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = unpack_unorm2x16_to_float(a[gid]);
}

kernel void k_unpack2(device const uint* a  [[buffer(0)]],
                      device float2* out     [[buffer(1)]],
                      device uint* passthru  [[buffer(2)]],
                      uint gid [[thread_position_in_grid]]) {
    uint v = a[gid];
    passthru[gid] = v;
    out[gid] = unpack_unorm2x16_to_float(v);
}

// standalone single-op reductions to isolate byte+2 (0x54 vs 0x56) per op.
kernel void k_rmax(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) { out[gid] = simd_max(a[gid]); }
kernel void k_rmin(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) { out[gid] = simd_min(a[gid]); }
kernel void k_rand(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) { out[gid] = simd_and(a[gid]); }
kernel void k_ror(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]],
                  uint gid [[thread_position_in_grid]]) { out[gid] = simd_or(a[gid]); }
kernel void k_rxor(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) { out[gid] = simd_xor(a[gid]); }
kernel void k_rfadd(device const float* a [[buffer(0)]], device float* out [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) { out[gid] = simd_sum(a[gid]); }
