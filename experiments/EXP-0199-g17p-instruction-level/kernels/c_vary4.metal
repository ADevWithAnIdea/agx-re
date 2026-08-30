// c_vary4.metal -- EXP-0199 carrier for vary_slot.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// FOUR varyings whose values are widely separated CONSTANTS (the same value at
// all three vertices, so interpolation cannot blur them into each other).  The
// fragment shader copies each varying straight into its own colour channel:
//
//   colour = (v0, v1, v2, v3) = (1000, 2000, 3000, 4000)   at every pixel
//
// That makes the observable a per-channel IDENTITY read-out of the varying slot
// assignment.  If `vary_slot.slot` selects which varying a vary_store writes,
// changing it must make one channel pick up ANOTHER channel's value (or lose its
// own), and WHICH value appears names the slot that was actually used.  A
// constant-oracle failure is impossible: the four expected values are distinct
// and known, and any permutation, duplication or dropout is directly readable.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
    float  v1;
    float  v2;
    float  v3;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0 = 1000.0f;
    o.v1 = 2000.0f;
    o.v2 = 3000.0f;
    o.v3 = 4000.0f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.v0, in.v1, in.v2, in.v3);
}
