// k_sdiv.metal -- EXP-0163 SIMD carrier WITH DIVERGENCE and a partially active
// mask.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  EXP-0155's `c_simd` is deliberately divergence-free ("NO divergence
// anywhere"), which is the right choice for decoding operand fields but removes
// the one thing a ballot is FOR: a non-trivial active mask.  If any byte of
// simd_ballot or simd_shuffle carries a scope, a mask source or an
// exec-mask-interaction rule, a program in which every lane is always active
// cannot show it.
//
// Here the SIMD ops are executed under a data-dependent branch, so the active
// mask is a proper subset of the group, and the ballot / shuffle results depend
// on WHICH lanes are live.  The inactive lanes still write a distinct marker, so
// "the branch went the other way" is separable from "the op returned something
// else".  Per EXP-0115 no barrier is used inside divergent control flow.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out        [[buffer(0)]],
                   device const uint *in   [[buffer(1)]],
                   uint tid                [[thread_position_in_grid]],
                   uint lane               [[thread_index_in_simdgroup]])
{
    uint  u = in[tid];
    float f = as_type<float>(in[32 + tid]);
    device uint *o = out + lane * 16u;
    for (uint k = 0u; k < 16u; ++k) o[k] = 0xC0DE0000u + k;

    if ((u & 4u) != 0u) {                    // a data-dependent, non-uniform branch
        simd_vote vb = simd_ballot((u & 8u) != 0u);
        uint mask = uint(static_cast<simd_vote::vote_t>(vb));
        uint b    = simd_broadcast(u, 5u);
        uint x    = simd_shuffle_xor(u, 2u);
        o[0] = mask;
        o[1] = b;
        o[2] = x;
        o[3] = simd_sum(u);
        o[4] = simd_max(u);
        o[5] = as_type<uint>(simd_sum(f));
        o[6] = uint(static_cast<simd_vote::vote_t>(simd_ballot(true)));
        o[7] = simd_shuffle(u, (lane + 1u) & 31u);
    } else {
        simd_vote vb = simd_ballot((u & 16u) != 0u);
        o[8]  = uint(static_cast<simd_vote::vote_t>(vb));
        o[9]  = simd_broadcast(u, 3u);
        o[10] = simd_shuffle_up(u, 1u);
        o[11] = simd_sum(u);
    }
    o[12] = simd_broadcast(u, 0u);           // reconverged
    o[13] = uint(static_cast<simd_vote::vote_t>(simd_ballot((u & 32u) != 0u)));
    o[14] = simd_shuffle_down(u, 3u);
    o[15] = lane;
}
