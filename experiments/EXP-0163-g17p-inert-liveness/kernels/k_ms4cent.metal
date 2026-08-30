// k_ms4cent.metal -- EXP-0163 carrier for iter_at.loc / iter.b9 / frag_tile_setup
// at rasterSampleCount 4.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY THIS CARRIER EXISTS.  EXP-0155 swept `iter_at.loc` (db.json enum
// 1 = centroid, 3 = sample) on ONE carrier only, `c_cent1`, which is built at
// rasterSampleCount == 1.  At one sample the centroid, the sample point and the
// pixel centre are THE SAME POINT, so no value of a location selector can move
// any observable -- the field was structurally unreachable, not inert.  Here the
// pass is 4x multisampled and resolved, so centroid / per-sample / centre
// interpolation land on genuinely different positions inside every partially
// covered pixel and the resolve makes that difference a read-back float.
//
// The per-vertex values carry LARGE gradients so a sub-pixel position change is
// numerically large: v0 spans 0..3000 across the triangle, and the observation
// is the whole 16x16 attachment (hash + probe pixels), so a change at ANY edge
// pixel is detected.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0 [[centroid_perspective]];
    float  v1 [[sample_perspective]];
    float  v2 [[center_perspective]];
    float  v3 [[centroid_no_perspective]];
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 3000.0f * f;                       // huge gradient: sub-pixel moves show
    o.v1  = 1700.0f - 900.0f * f * f;
    o.v2  = 40.0f   + 610.0f * f;
    o.v3  = 7.0f    + 1300.0f * (f * f - f);
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.v0, in.v1, in.v2, in.v3);
}
