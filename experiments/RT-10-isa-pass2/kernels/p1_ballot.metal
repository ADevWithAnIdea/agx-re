#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: simd_ballot with a DIFFERENT predicate than RT-ISA-FIX (lane<5).
// Predicate lane>=16 -> upper-half mask 0xFFFF0000 when all 32 active.
kernel void k(device uint* out [[buffer(0)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    simd_vote v = simd_ballot(lane >= 16u);
    out[tid] = (uint)((simd_vote::vote_t)v);
}
