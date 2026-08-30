// c_depth.metal -- EXP-0199 fragment carrier for frag_depth_store.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// Derived from OUR OWN experiments/EXP-0155-g17p-emit-tex-frag/kernels/
// c_depth.metal, with ONE deliberate change that makes the oracle DISCRIMINATING
// at the instruction level: the depth output and the colour output are DIFFERENT
// per-pixel functions of the same interpolated varying.
//
//   depth      = v0            (an interpolated gradient, distinct per pixel)
//   color.r    = v0 * 0.25 + 0.5   (a DIFFERENT gradient, same source)
//   color.gba  = constants
//
// Why: EXP-0155 gave depth and colour the SAME value, so a case that changed
// both identically was indistinguishable from a case that changed neither
// observable independently.  Here the depth attachment carries information the
// colour attachment does not, and the host oracle predicts a 3-element vector of
// DISTINCT depth values (one per probe pixel), never a constant.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
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
    o.v0  = 0.125f + 0.25f * f;
    return o;
}

fragment FOut f_main(VOut in [[stage_in]])
{
    FOut o;
    o.color = float4(in.v0 * 0.25f + 0.5f, 0.5f, 0.25f, 1.0f);
    o.depth = in.v0;
    return o;
}
