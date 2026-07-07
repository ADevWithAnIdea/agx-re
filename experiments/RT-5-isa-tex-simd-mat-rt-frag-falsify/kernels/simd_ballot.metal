#include <metal_stdlib>
using namespace metal;

// simd_ballot(lane < 5) -> active-lane bitmask 0x1F. Every lane writes it.
kernel void k(device uint* out [[buffer(0)]],
              uint lane [[thread_index_in_threadgroup]]) {
    simd_vote v = simd_ballot(lane < 5);
    out[lane] = (uint)((simd_vote::vote_t)v);
}
