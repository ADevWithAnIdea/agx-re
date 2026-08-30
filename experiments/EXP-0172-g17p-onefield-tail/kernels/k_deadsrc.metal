// k_deadsrc.metal -- EXP-0172 DEAD-SOURCE carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  Three of this experiment's fields live in the same byte -- the
// ubiquitous `0x54` operand byte at byte+2:
//   * `simd_ballot.cache`   (byte+2, all 8 bits modelled)
//   * `simd_shuffle.cache`  (bit 17 -- the ONLY bit of byte+2 db.json models,
//                            and the only bit its match leaves free)
//   * `irotate.b2`          (declared width 8, but the match pins bit16 and
//                            bits18..23, leaving the SAME bit 17 free)
// db.json's own vocabulary for a byte in this role, on `falu_acc`, is "a source
// cache / LAST-USE hint" (RT-1a-FIX).  If that is what it is, the dimension it
// controls is WHETHER THE SOURCE REGISTER IS READ AGAIN AFTER THIS OP -- and
// every carrier swept so far (EXP-0155's, EXP-0163's k_sball / k_scache /
// k_stype / k_sdiv, and this experiment's k_rot / k_rot2) reuses its sources
// heavily.  Under the promotion rule those are all ONE carrier in the dimension
// that matters, which is exactly the trap `iter_at.loc` fell into.
//
// Here every operand is loaded, consumed by exactly ONE operation, and never
// referenced again, so each source register is dead at the instruction under
// test.  Paired with k_rot / k_sball / k_stype (all live-source), this is the
// controlled comparison a last-use hint would need.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    device uint *o = out + lane * 16u;
    uint t = tid & 31u;

    o[0]  = rotate(in[(t +  0u) & 31u], 5u);
    o[1]  = rotate(in[(t +  1u) & 31u], 13u);
    o[2]  = rotate(in[(t +  2u) & 31u], 1u);
    o[3]  = rotate(in[(t +  3u) & 31u], 31u);
    o[4]  = simd_broadcast(in[(t + 4u) & 31u], 3u);
    o[5]  = simd_shuffle_xor(in[(t + 5u) & 31u], 2u);
    o[6]  = simd_shuffle_up(in[(t + 6u) & 31u], 1u);
    o[7]  = simd_shuffle_down(in[(t + 7u) & 31u], 3u);
    o[8]  = uint(static_cast<simd_vote::vote_t>(
                     simd_ballot((in[(t + 8u) & 31u] & 1u) != 0u)));
    o[9]  = uint(static_cast<simd_vote::vote_t>(
                     simd_ballot((in[(t + 9u) & 31u] & 2u) != 0u)));
    o[10] = uint(static_cast<quad_vote::vote_t>(
                     quad_ballot((in[(t + 10u) & 31u] & 4u) != 0u)));
    o[11] = simd_any((in[(t + 11u) & 31u] & 8u) != 0u) ? 1u : 0u;
    o[12] = simd_all((in[(t + 12u) & 31u] & 0x80000000u) == 0u) ? 2u : 0u;
    o[13] = quad_shuffle(in[(t + 13u) & 31u], 2u);
    o[14] = simd_shuffle(in[(t + 14u) & 31u], 11u);
    o[15] = rotate(in[(t + 15u) & 31u], 8u);
}
