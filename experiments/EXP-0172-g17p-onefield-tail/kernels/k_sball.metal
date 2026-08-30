// k_sball.metal -- EXP-0163 SIMD-BALLOT FORM carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  db.json distinguishes two simd_ballot forms by the byte+1 high nibble:
// 0x07 = simd_active_threads_mask / simd_any / simd_all, 0x17 =
// simd_ballot(predicate) -- and says the byte+6..+9 tail is "form/mask-format",
// with "value-enum maps for psrctype / form / form_sig [needing] a splice
// testbed".  EXP-0155 had exactly ONE ballot arm, of the predicate form, whose
// result was stored once.  `cache` (byte+2) was 0x54 there and is 0x54 here too,
// but this carrier surrounds it with every other ballot form the language
// offers and consumes each result several times, so if byte+2 gates anything
// about how the mask is produced or kept, it has the widest chance to show.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out        [[buffer(0)]],
                   device const uint *in   [[buffer(1)]],
                   uint tid                [[thread_position_in_grid]],
                   uint lane               [[thread_index_in_simdgroup]])
{
    uint u = in[tid];
    float f = as_type<float>(in[32 + tid]);

    uint m_act  = uint(static_cast<simd_vote::vote_t>(simd_active_threads_mask()));
    uint m_ball = uint(static_cast<simd_vote::vote_t>(simd_ballot((u & 1u) != 0u)));
    uint m_b2   = uint(static_cast<simd_vote::vote_t>(simd_ballot(f > 3.0f)));
    uint m_q    = uint(static_cast<quad_vote::vote_t>(quad_ballot((u & 2u) != 0u)));
    bool anyv   = simd_any((u & 4u) != 0u);
    bool allv   = simd_all((u & 0x80000000u) == 0u);
    bool qany   = quad_any((u & 8u) != 0u);
    bool qall   = quad_all(f > 0.0f);

    // Consume each mask several times and feed it back into the SIMD network.
    uint mix = m_act ^ (m_ball * 3u) ^ (m_b2 << 1) ^ (m_q * 5u);
    uint bc  = simd_broadcast(mix, 5u);
    uint sm  = simd_sum(popcount(m_ball) + popcount(m_act));

    device uint *o = out + lane * 16u;
    o[0] = m_act;  o[1] = m_ball; o[2] = m_b2;  o[3] = m_q;
    o[4] = anyv ? 1u : 0u;  o[5] = allv ? 2u : 0u;
    o[6] = qany ? 4u : 0u;  o[7] = qall ? 8u : 0u;
    o[8] = mix;    o[9] = bc;     o[10] = sm;
    o[11] = m_act & m_ball;
    o[12] = m_ball | m_b2;
    o[13] = popcount(m_act);
    o[14] = uint(static_cast<simd_vote::vote_t>(simd_ballot(m_ball > lane)));
    o[15] = mix + bc + sm;
}
