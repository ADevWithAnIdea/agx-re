// c_depth.metal -- EXP-0143 carrier for frag_depth_store.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// The fragment shader writes an INTERPOLATED [[depth(any)]] value (not a
// constant), so the depth attachment read-back is a per-pixel gradient: any
// change to the depth store that alters WHAT is written, or WHETHER it is
// written, is visible against both the gradient and the clear value.
// Colour channel 0 carries the same value so a colour/depth divergence is
// distinguishable from a shader-wide change.

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
    o.color = float4(in.v0, 0.5f, 0.25f, 1.0f);
    o.depth = in.v0;
    return o;
}
