// k_rot2.metal -- EXP-0172 irotate carrier B, structurally different from
// k_rot.metal: the rotate results feed the SIMD network and a threadgroup
// round-trip instead of going straight to a device store, the sources are 16-bit
// and vector-lane derived rather than a single scalar load, and the rotate
// amounts are chosen so that the pre- and post-rotate values are distinguishable
// at every probe lane.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  EXP-0166's recommendation #4 is literally "a second carrier for
// `irotate.b2` -- the only field left blocking `irotate`, and EXP-0146's arm can
// never supply it".  This is that carrier.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    threadgroup uint tg[32];

    uint  u  = in[tid & 31u];
    ushort s = ushort(u & 0xFFFFu);

    uint a = rotate(u, 11u);
    tg[lane] = a;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint b = rotate(tg[(lane + 7u) & 31u], 19u);
    uint c = rotate(simd_broadcast(u, 3u), 23u);
    uint d = uint(rotate(s, ushort(4)));
    uint e = rotate(u ^ (lane * 0x9E3779B1u), 29u);

    device uint *o = out + lane * 16u;
    o[0]  = a;  o[1]  = b;  o[2]  = c;  o[3]  = d;  o[4]  = e;
    o[5]  = simd_sum(a);
    o[6]  = simd_broadcast(b, 5u);
    o[7]  = a ^ b ^ c ^ d ^ e;
    o[8]  = rotate(a, 2u);
    o[9]  = rotate(b, 6u);
    o[10] = rotate(c ^ d, 10u);
    o[11] = tg[(lane + 1u) & 31u];
    o[12] = popcount(a) + popcount(b);
    o[13] = u;
    o[14] = (a >> 16) | (e << 16);
    o[15] = a + b + c + d + e;
}
