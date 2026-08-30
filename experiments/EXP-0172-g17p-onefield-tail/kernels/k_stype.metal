// k_stype.metal -- EXP-0163 SIMD OPERAND-TYPE / SHUFFLE-FORM carrier.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  `simd_shuffle.rsv9` is byte+9, the LAST byte of the op, and db.json
// describes it as "reserved/rotate-tail" -- explicitly noting that the mode-0x06
// rotate/fill form carries a distinct tail (`00 14 a2`).  EXP-0155 swept it on
// two arms, both 32-bit `uint` shuffles (a static broadcast and an xor/down).
// The rotate/fill forms, the quad-scope forms, the dynamic-lane forms and the
// 16-bit and 64-bit operand widths were never present, so a field that only
// carries a value in those forms could not move.
//
// This carrier emits, in one kernel: quad shuffles, simd shuffle-and-fill (the
// rotate form), rotate-up/down, dynamic (register) lane indices, and half /
// ushort / float / uint2 operand types.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out        [[buffer(0)]],
                   device const uint *in   [[buffer(1)]],
                   uint tid                [[thread_position_in_grid]],
                   uint lane               [[thread_index_in_simdgroup]])
{
    uint   u  = in[tid];
    float  f  = as_type<float>(in[32 + tid]);
    half   h  = half(f * 0.03125f);
    ushort s  = ushort(u & 0xFFFFu);
    uint2  u2 = uint2(u, u ^ 0xA5A5A5A5u);

    // Static and dynamic lane selectors.
    uint  q0 = quad_shuffle(u, 2u);
    uint  q1 = quad_shuffle_xor(u, 1u);
    uint  q2 = quad_shuffle_up(u, 1u);
    uint  q3 = quad_shuffle_down(u, 2u);
    uint  d0 = simd_shuffle(u, (u + lane) & 31u);       // dynamic lane
    half  hs = simd_shuffle(h, 7u);                     // 16-bit float operand
    ushort ss = simd_shuffle(s, 11u);                   // 16-bit uint operand
    float fs = simd_shuffle_xor(f, 4u);                 // 32-bit float operand
    uint2 vs = simd_shuffle(u2, 13u);                   // 64-bit (vector) operand

    // The rotate / shuffle-and-fill forms (db.json mode 0x06).
    uint r0 = simd_shuffle_and_fill_up(u, u + 1u, 3u);
    uint r1 = simd_shuffle_and_fill_down(u, u + 2u, 5u);
    uint r2 = simd_shuffle_rotate_up(u, 6u);
    uint r3 = simd_shuffle_rotate_down(u, 7u);

    device uint *o = out + lane * 16u;
    o[0]  = q0;  o[1]  = q1;  o[2]  = q2;  o[3]  = q3;
    o[4]  = d0;
    o[5]  = uint(as_type<ushort>(hs));
    o[6]  = uint(ss);
    o[7]  = as_type<uint>(fs);
    o[8]  = vs.x; o[9] = vs.y;
    o[10] = r0;  o[11] = r1;  o[12] = r2;  o[13] = r3;
    o[14] = quad_broadcast(u, 3u);
    o[15] = uint(static_cast<quad_vote::vote_t>(quad_ballot((u & 2u) != 0u)));
}
