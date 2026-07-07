#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: simd_active_threads_mask (unconditional active mask, byte+1 hi-nibble 0).
kernel void k(device uint* out [[buffer(0)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    simd_vote v = simd_active_threads_mask();
    out[tid] = (uint)((simd_vote::vote_t)v);
}
