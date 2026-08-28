// c_at.metal -- EXP-0143 carrier for iter_at (the interpolate-at SETUP op).
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// The MSL pull model (metal::interpolant<>) with interpolate_at_offset() forces
// the compiler to emit the iter_at setup op at rasterSampleCount == 1, where
// centroid/sample would otherwise degenerate to pixel centre and be
// unobservable.  EXP-0111 established that interpolate_at_offset VIOLATES its
// documented contract on this hardware, so this carrier's oracle is DERIVED
// FROM THE OBSERVED BASELINE, never from Apple's documented semantics.
//
// Channel 0 = centre-interpolated v0, channel 1 = offset-interpolated v0;
// channels 2/3 the same for v1.  Centre and offset reads of the SAME varying
// therefore sit side by side in one pixel.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
    float  v1;
};

struct FIn {
    float4 pos [[position]];
    interpolant<float, interpolation::perspective> v0;
    interpolant<float, interpolation::perspective> v1;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 1.0f  + f;
    o.v1  = 10.0f + f * f;
    return o;
}

fragment float4 f_main(FIn in [[stage_in]])
{
    float a = in.v0.interpolate_at_center();
    float b = in.v0.interpolate_at_offset(float2(0.375f, -0.25f));
    float c = in.v1.interpolate_at_center();
    float d = in.v1.interpolate_at_offset(float2(-0.375f, 0.25f));
    return float4(a, b, c, d);
}
