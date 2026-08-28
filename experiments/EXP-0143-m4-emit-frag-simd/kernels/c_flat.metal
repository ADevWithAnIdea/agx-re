// c_flat.metal -- EXP-0143 carrier for iter_flat ([[flat]] varyings, no
// barycentric interpolation).  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// Four [[flat]] varyings whose provoking-vertex values are distinct powers of
// two, so a slot/selector mix-up is unambiguous in the read-back float.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  f0 [[flat]];
    float  f1 [[flat]];
    float  f2 [[flat]];
    float  f3 [[flat]];
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.f0 = 3.0f  + f;
    o.f1 = 33.0f + f;
    o.f2 = 333.0f + f;
    o.f3 = 3333.0f + f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.f0, in.f1, in.f2, in.f3);
}
