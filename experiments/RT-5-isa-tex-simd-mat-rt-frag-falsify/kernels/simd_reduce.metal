#include <metal_stdlib>
using namespace metal;

// simd_sum over lanes 0..31 -> 496 written to every lane.
// XOR of 0..31 = 0; max = 31; min = 0; product would overflow.
// Splicing byte0 bit7 (0xbf<->0x3f) and byte+1 op-select reveals the op.
kernel void k(device uint* out [[buffer(0)]],
              uint lane [[thread_index_in_threadgroup]]) {
    uint v = lane;                 // distinct per lane: 0..31
    out[lane] = simd_sum(v);
}
