// k_scache.metal -- EXP-0163 SIMD RESULT-REUSE carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  `simd_ballot.cache` (byte+2, 8 bits) and `simd_shuffle.cache` (byte+2
// bit 1) were each swept on ONE arm of EXP-0155's `c_simd`, where every SIMD
// result is computed once and immediately stored once.  If "cache" is a
// register-cache / value-liveness hint -- the reading the name suggests -- then
// a value that is produced and consumed exactly once, with no other consumer and
// no reuse distance, is precisely the case in which such a hint cannot change
// anything.  This carrier attacks that directly:
//
//   * every SIMD result is consumed MANY times, at long distance, by later
//     arithmetic and by FURTHER SIMD ops that take it as their source;
//   * one shuffle's result is the lane index of the next shuffle, so the value
//     is on the critical path of the cross-lane network itself;
//   * a ballot result feeds a shuffle and a reduce, then is stored again at the
//     end, so it must stay live across the whole kernel;
//   * a loop re-reads the same results on each iteration, maximising reuse
//     distance and register pressure.
//
// No divergence and no barriers (EXP-0115: simdgroup_barrier is not a universal
// no-op under divergent call patterns), so this stays a clean single SIMD group.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out        [[buffer(0)]],
                   device const uint *in   [[buffer(1)]],
                   uint tid                [[thread_position_in_grid]],
                   uint lane               [[thread_index_in_simdgroup]])
{
    uint  u = in[tid];
    float f = as_type<float>(in[32 + tid]);

    // A ballot result that MANY later ops consume.
    simd_vote vb = simd_ballot((u & 1u) != 0u);
    uint mask = uint(static_cast<simd_vote::vote_t>(vb));

    // A broadcast whose result is reused as the lane selector of a second
    // shuffle, as an arithmetic operand, and again at the very end.
    uint b0 = simd_broadcast(u, 5u);
    uint b1 = simd_shuffle(u, (b0 ^ mask) & 31u);
    uint b2 = simd_shuffle_xor(b0 + b1, 1u);

    // Long-distance reuse: accumulate over a loop that re-reads b0/b1/mask.
    uint acc = 0u;
    for (uint k = 0u; k < 8u; ++k) {
        acc += (b0 >> (k & 7u)) + (b1 * (k + 1u)) + (mask & (1u << (k & 31u)));
    }

    // Feed the cross-lane network again from the reused values.
    uint r0 = simd_sum(acc);
    uint r1 = simd_max(b0 ^ b2);
    float r2 = simd_sum(f * float(b0 & 255u));

    device uint *o = out + lane * 16u;
    o[0]  = mask;
    o[1]  = b0;
    o[2]  = b1;
    o[3]  = b2;
    o[4]  = acc;
    o[5]  = r0;
    o[6]  = r1;
    o[7]  = as_type<uint>(r2);
    o[8]  = b0 + mask;              // mask and b0 still live here
    o[9]  = b1 ^ mask;
    o[10] = simd_broadcast(acc, 9u);
    o[11] = simd_shuffle_up(b2, 3u);
    o[12] = simd_shuffle_down(b1, 4u);
    o[13] = uint(static_cast<simd_vote::vote_t>(simd_ballot(b0 > b1)));
    o[14] = b0 * 3u + b1 * 5u + b2 * 7u;
    o[15] = mask + acc + r0 + r1;
}
