// k_cent.metal -- EXP-0163 MINIMAL-DELTA carrier for iter_at.loc.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// This program is deliberately the SAME SHAPE as EXP-0155's `c_cent.metal`
// carrier (two centroid_perspective and two sample_perspective varyings written
// straight to the colour attachment).  EXP-0163 builds it TWICE, at
// rasterSampleCount 1 and rasterSampleCount 4, and sweeps iter_at.loc on both.
//
// That is the cleanest possible test of the experiment's central question: the
// MSL, the compiled bytes and every field value are identical; the ONLY
// difference between the two arms is the sample count, i.e. whether the
// location the field selects is a distinguishable place in the pixel at all.
// EXP-0155 swept iter_at only at rasterSampleCount 1 and read 256/256 inert.
//
// The per-vertex values carry large gradients so a sub-pixel position change is
// numerically large in the read-back.
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
    o.v0  = 3000.0f * f;
    o.v1  = 1700.0f - 900.0f * f * f;
    o.v2  = 40.0f   + 610.0f * f;
    o.v3  = 7.0f    + 1300.0f * (f * f - f);
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.v0, in.v1, in.v2, in.v3);
}
