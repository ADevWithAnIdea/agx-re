#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: simd_shuffle_up delta 2 (not tested in RT-ISA-FIX).
kernel void k(device uint* out [[buffer(0)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane*3u + 1u;
    out[tid] = simd_shuffle_up(v, 2);
}
