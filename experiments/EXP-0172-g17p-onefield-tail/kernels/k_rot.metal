// k_rot.metal -- EXP-0172 irotate carrier A (rotate-by-immediate, several
// amounts and several source classes).  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  `irotate.b2` is the LAST field blocking `irotate` from emittable.
// EXP-0146 published "256 values tested (full 8-bit dense)" for it; EXP-0166
// (DEF-0166-1) showed that sweep reached **32 of 256 encodings**, because it
// built its bytes through `isadb.assemble()`, whose OR could not clear the bits
// `irotate`'s own match constant sets.  Worse, `irotate`'s match pins bit16 to 0
// and bits18..23 to 0x15, so of the eight bits db.json declares as `b2` exactly
// ONE -- bit 17 -- is free while still decoding as `irotate`.
//
// This carrier exists to sweep byte+2 densely and honestly (256 DISTINCT
// spliced byte strings, verified in the raw) on a program where the rotate
// results are all separately observable.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tid  [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    uint u = in[tid & 31u];

    uint r1  = rotate(u, 1u);
    uint r5  = rotate(u, 5u);
    uint r13 = rotate(u ^ 0x5A5A5A5Au, 13u);
    uint r17 = rotate(u + 0x01234567u, 17u);
    uint r31 = rotate(u * 3u, 31u);
    uint r8  = rotate(u, 8u);

    device uint *o = out + lane * 16u;
    o[0]  = r1;   o[1]  = r5;   o[2]  = r13;
    o[3]  = r17;  o[4]  = r31;  o[5]  = r8;
    o[6]  = r1 ^ r5;
    o[7]  = r13 + r17;
    o[8]  = r31 * 3u;
    o[9]  = r8 | r1;
    o[10] = popcount(r5 ^ r13);
    o[11] = rotate(r1, 3u);
    o[12] = rotate(r5, 7u);
    o[13] = u;
    o[14] = r1 + r5 + r13 + r17 + r31 + r8;
    o[15] = (r1 & 0xFFFFu) | (r31 << 16);
}
