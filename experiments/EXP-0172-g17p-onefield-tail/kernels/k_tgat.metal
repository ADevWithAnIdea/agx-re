// k_tgat.metal -- EXP-0172 THREADGROUP-ATOMIC / frame-marker carrier.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  `frame_marker_compact` is the 2-byte `60 <b1>` word db.json describes as
// a "compact frame/scope marker ... precedes a threadgroup-atomic store or a
// divergent control-flow block", located by an EXP-M4-01 length probe in
// k_atomics_tg and k_atomics and never swept on hardware at all (`b1` is
// `tokenization-only`, framing only).  Its length anchor came from a threadgroup
// atomics kernel, so that is the shape reproduced here: threadgroup atomics of
// several kinds, under divergence, with the results read back per lane.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    threadgroup atomic_uint acc[8];
    if (lane < 8u)
        atomic_store_explicit(&acc[lane], 0x1000u * (lane + 1u), memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);

    uint u = in[tid & 31u];

    if ((u & 1u) != 0u)
        atomic_fetch_add_explicit(&acc[0], u & 0xFFu, memory_order_relaxed);
    else
        atomic_fetch_xor_explicit(&acc[1], u & 0xFFu, memory_order_relaxed);

    atomic_fetch_or_explicit(&acc[2], 1u << (lane & 31u), memory_order_relaxed);
    atomic_fetch_max_explicit(&acc[3], u & 0xFFFFu, memory_order_relaxed);
    atomic_fetch_min_explicit(&acc[4], u | 0xF0000000u, memory_order_relaxed);
    atomic_fetch_and_explicit(&acc[5], ~(1u << (lane & 15u)), memory_order_relaxed);

    if ((u & 2u) != 0u) {
        atomic_fetch_add_explicit(&acc[6], 3u, memory_order_relaxed);
        if ((u & 4u) != 0u)
            atomic_fetch_add_explicit(&acc[7], 5u, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);

    device uint *o = out + lane * 16u;
    for (uint k = 0u; k < 8u; ++k)
        o[k] = atomic_load_explicit(&acc[k], memory_order_relaxed);
    o[8]  = u;
    o[9]  = lane;
    o[10] = o[0] ^ o[1];
    o[11] = o[2] + o[3];
    o[12] = o[4] - o[5];
    o[13] = o[6] * 7u + o[7];
    o[14] = simd_sum(o[0]);
    o[15] = o[0] + o[1] + o[2] + o[3] + o[4] + o[5] + o[6] + o[7];
}
