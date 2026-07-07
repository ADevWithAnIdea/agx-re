#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: simd_broadcast from lane 7 (RT-ISA-FIX used lane 3), value = lane*3+1.
kernel void k(device uint* out [[buffer(0)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane*3u + 1u;
    out[tid] = simd_broadcast(v, 7);
}
