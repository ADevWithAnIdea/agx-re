#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: simd_shuffle_xor mask 1 (RT-ISA-FIX used 3).
kernel void k(device uint* out [[buffer(0)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane*3u + 1u;
    out[tid] = simd_shuffle_xor(v, 1);
}
