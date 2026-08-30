// k_cfdiv.metal -- EXP-0172 DIVERGENT-CONTROL-FLOW carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  `n4_cf_word` is the 4-byte compute control word `04 01 00 <b3>` that
// EXP-M4-13 R7 found immediately before a pop_reconverge (60 of 68 occurrences),
// an rt_ray_mem (5) or a threadgroup_barrier (1) in divergent-CF and ray-query
// kernels.  `b3` is `tokenization-only` -- framing only, never swept.  This
// carrier is nested, data-dependent divergence with reconvergence points and a
// barrier outside the divergent region (EXP-0115: no barrier inside divergence),
// i.e. the exact structural context the word was located in.
//
// The inactive path writes its own marker at every level, so "the branch went
// the other way" is separable from "the arithmetic returned something else".
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    uint  u = in[tid & 31u];
    float f = as_type<float>(in[32u + (tid & 31u)]);
    device uint *o = out + lane * 16u;
    for (uint k = 0u; k < 16u; ++k) o[k] = 0xC0DE0000u + k;

    uint acc = 0u;
    if ((u & 1u) != 0u) {
        acc += 11u;
        if ((u & 2u) != 0u) {
            acc += 101u;
            for (uint k = 0u; k < (u & 3u) + 1u; ++k) acc = acc * 3u + k;
            o[0] = acc;
        } else {
            acc ^= 0x5A5Au;
            o[1] = acc;
        }
        o[2] = acc + 1u;
    } else {
        acc += 22u;
        if ((u & 4u) != 0u) {
            acc *= 7u;
            o[3] = acc;
        } else {
            acc = uint(f * 3.0f) + 13u;
            o[4] = acc;
        }
        o[5] = acc + 2u;
    }
    o[6] = acc;                                  // reconverged
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[7] = simd_sum(acc);
    o[8] = uint(static_cast<simd_vote::vote_t>(simd_ballot((u & 8u) != 0u)));

    uint w = 0u;
    while (w < 4u && ((u >> w) & 1u) == 0u) w++;  // divergent loop trip count
    o[9]  = w;
    o[10] = acc ^ w;
    o[11] = u;
    o[12] = lane;
    o[13] = simd_broadcast(acc, 3u);
    o[14] = as_type<uint>(f);
    o[15] = acc + w + lane;
}
