// k_ms4out.metal -- EXP-0163 PER-SAMPLE carrier for iter_at.loc / iter.b9.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// The resolve in k_ms4cent AVERAGES the four samples, which can hide a change
// that only permutes them.  Here the fragment stage takes [[sample_id]] -- which
// forces PER-SAMPLE execution -- and writes each sample's interpolated values
// straight into a device buffer at [[buffer(1)]], indexed
// (y * width + x) * 4 + sample_id.  Every sample's interpolated value is then
// separately observable with no averaging at all, so "centroid == sample" and
// "centroid != sample" are directly distinguishable.
//
// The buffer is pre-filled with 0xDEADBEEF by the harness, so a lane that never
// ran reads back as poison rather than as zero (FIELD-SWEEP-PROTOCOL sec.7.1).
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0 [[centroid_perspective]];
    float  v1 [[sample_perspective]];
    float  v2 [[center_perspective]];
    float  v3 [[sample_no_perspective]];
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

fragment float4 f_main(VOut in [[stage_in]],
                       uint sid [[sample_id]],
                       device float4 *out [[buffer(1)]])
{
    uint x = uint(in.pos.x);
    uint y = uint(in.pos.y);
    out[(y * 16u + x) * 4u + sid] = float4(in.v0, in.v1, in.v2, in.v3);
    return float4(in.v0, in.v1, in.v2, in.v3);
}
