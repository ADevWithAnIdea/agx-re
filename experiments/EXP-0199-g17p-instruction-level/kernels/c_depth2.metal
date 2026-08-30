// c_depth2.metal -- EXP-0199 amendment 01: the ADVERSARIAL SECOND depth carrier
// (Phase 5 of RE_EXPERIMENT_PROCESS_CORRECTIONS: repeat a surprising result with
// a carrier that differs in the dimension the claim is about).  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// It differs from c_depth.metal in EVERY dimension the depth claim depends on:
//   * the depth value is a DIFFERENT function of a DIFFERENT varying, and it is
//     DECREASING where c_depth's is increasing:  depth = 0.9 - 0.5*v1;
//   * the colour carries a THIRD, independent varying, so colour and depth do
//     not share a source at all (in c_depth they shared v0);
//   * two varyings are interpolated instead of one, so the fragment prologue
//     differs and the depth store is not adjacent to the same neighbours.
// If `frag_depth_store` is what puts the shader's depth output into the depth
// attachment, the host predictor DEPTH == 0.9 - 0.5*((PIX0.g - 0.125)/0.5) must
// hold here too, and the same byte mutations must move DEPTH alone here too.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v1;
    float  v2;
};

struct FOut {
    float4 color [[color(0)]];
    float  depth [[depth(any)]];
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v1  = 0.25f + 0.3f * f;
    o.v2  = 0.875f - 0.2f * f;
    return o;
}

fragment FOut f_main(VOut in [[stage_in]])
{
    FOut o;
    o.color = float4(0.375f, 0.125f + 0.5f * in.v1, in.v2, 1.0f);
    o.depth = 0.9f - 0.5f * in.v1;
    return o;
}
