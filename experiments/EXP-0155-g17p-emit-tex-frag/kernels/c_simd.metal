// c_simd.metal -- EXP-0143 carrier for the SIMD family
// (simd_reduce / simd_shuffle / simd_ballot).  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// One 32-thread threadgroup = exactly one SIMD group, NO divergence anywhere.
// EXP-0115 corrected EXP-0104: simdgroup_barrier is NOT universally a no-op --
// it breaks under divergent call patterns -- so this carrier is deliberately
// divergence-free and contains no barrier, and every SIMD result is written
// unconditionally by every lane.
//
// Each lane reads a distinct input word from buffer 1 and writes 16 result
// words to buffer 0 at out[lane*16 + k], so a spliced field's effect is
// attributable to one specific result slot and visible per lane.

#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out        [[buffer(0)]],
                   device const uint *in   [[buffer(1)]],
                   uint tid                [[thread_position_in_grid]],
                   uint lane               [[thread_index_in_simdgroup]])
{
    uint  u  = in[tid];
    float f  = as_type<float>(in[32 + tid]);

    uint  r_isum  = simd_sum(u);                        // simd_reduce int sum
    uint  r_umax  = simd_max(u);                        // simd_reduce umax
    int   r_smin  = simd_min(int(u) - 17);              // simd_reduce smin
    uint  r_ior   = simd_or(u);                         // simd_reduce ior
    uint  r_ixor  = simd_xor(u);                        // simd_reduce ixor
    float r_fsum  = simd_sum(f);                        // simd_reduce f32 sum
    float r_fprod = simd_product(f);                    // simd_reduce f32 product
    uint  r_scan  = simd_prefix_exclusive_sum(u);       // simd_reduce excl scan
    uint  r_iscan = simd_prefix_inclusive_sum(u);       // simd_reduce incl scan
    uint  r_quad  = quad_sum(u);                        // quad-scope reduce

    uint  r_bcast = simd_broadcast(u, 5u);              // simd_shuffle bcast
    uint  r_shuf  = simd_shuffle(u, (lane + 3u) & 31u); // simd_shuffle dynamic
    uint  r_xor1  = simd_shuffle_xor(u, 1u);            // simd_shuffle xor
    uint  r_up    = simd_shuffle_up(u, 2u);             // simd_shuffle up
    uint  r_down  = simd_shuffle_down(u, 2u);           // simd_shuffle down

    simd_vote  vb  = simd_ballot((u & 1u) != 0u);       // simd_ballot(predicate)
    uint  r_ballot = uint(static_cast<simd_vote::vote_t>(vb));

    device uint *o = out + lane * 16u;
    o[0]  = r_isum;
    o[1]  = r_umax;
    o[2]  = uint(r_smin);
    o[3]  = r_ior;
    o[4]  = r_ixor;
    o[5]  = as_type<uint>(r_fsum);
    o[6]  = as_type<uint>(r_fprod);
    o[7]  = r_scan;
    o[8]  = r_iscan;
    o[9]  = r_quad;
    o[10] = r_bcast;
    o[11] = r_shuf;
    o[12] = r_xor1;
    o[13] = r_up;
    o[14] = r_down;
    o[15] = r_ballot;
}
