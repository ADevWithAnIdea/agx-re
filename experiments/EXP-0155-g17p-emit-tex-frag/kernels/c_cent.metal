// c_cent.metal -- EXP-0143 carrier for iter_at (the interpolate-at SETUP op),
// reached through the centroid/sample interpolation qualifiers rather than the
// pull model.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// Rendered MULTISAMPLED (rasterSampleCount 4) so centroid and per-sample
// interpolation are genuinely distinct from pixel-centre interpolation and the
// setup op's result is observable in the resolved/first-sample pixel.
//
// v0/v1 are centroid_perspective, v2/v3 sample_perspective; each carries a
// distinct, asymmetric per-vertex value so a slot or location mix-up is
// numerically visible.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0 [[centroid_perspective]];
    float  v1 [[centroid_perspective]];
    float  v2 [[sample_perspective]];
    float  v3 [[sample_perspective]];
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 1.0f    + f;
    o.v1  = 10.0f   + f * f;
    o.v2  = 100.0f  - 3.0f * f;
    o.v3  = 1000.0f + 5.0f * f * f - 2.0f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.v0, in.v1, in.v2, in.v3);
}
