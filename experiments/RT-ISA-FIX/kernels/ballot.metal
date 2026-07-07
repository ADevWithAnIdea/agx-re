#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    simd_vote v = simd_ballot(lane < 5);
    out[tid] = (uint)((simd_vote::vote_t)v);
}
