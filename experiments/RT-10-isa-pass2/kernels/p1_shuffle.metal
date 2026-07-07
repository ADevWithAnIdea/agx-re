#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: dynamic simd_shuffle(v, srcLane) with a data-dependent source lane.
kernel void k(device uint* out [[buffer(0)]],
              device const uint* in [[buffer(1)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane*3u + 1u;
    uint srcLane = in[tid] & 31u;
    out[tid] = simd_shuffle(v, srcLane);
}
