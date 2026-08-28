// c_mask.metal -- EXP-0143 second probe for the 0x57 fragment-stage op:
// an explicit [[sample_mask]] output (the "target mask" form) rather than
// discard_fragment().  OUR OWN MSL.  Clean-room: OWN-SHADER.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
};

struct FOut {
    float4 color [[color(0)]];
    uint   mask  [[sample_mask]];
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 1.0f + f;
    return o;
}

fragment FOut f_main(VOut in [[stage_in]])
{
    FOut o;
    o.color = float4(in.v0, 7.0f, 11.0f, 13.0f);
    o.mask  = (in.v0 < 2.0f) ? 0u : 0xFFFFFFFFu;
    return o;
}
