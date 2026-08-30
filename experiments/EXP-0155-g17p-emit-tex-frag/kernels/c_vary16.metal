// c_vary16.metal -- EXP-0143 wide-varying vertex carrier: 12 user varyings plus
// [[position]] pushes vary_store past slot 7, exercising the out_slot_hi bit
// and giving a larger vary_slot / vary_store corpus.  OUR OWN MSL.
// Clean-room: OWN-SHADER.

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  a0; float a1; float a2; float a3;
    float  a4; float a5; float a6; float a7;
    float  a8; float a9; float a10; float a11;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.a0  = 1.0f    + f;      o.a1  = 10.0f   + f * f;
    o.a2  = 100.0f  - 3.0f*f; o.a3  = 1000.0f + 5.0f*f*f - 2.0f*f;
    o.a4  = 2.0f    + f;      o.a5  = 20.0f   + f * f;
    o.a6  = 200.0f  - 3.0f*f; o.a7  = 2000.0f + 5.0f*f*f - 2.0f*f;
    o.a8  = 3.0f    + f;      o.a9  = 30.0f   + f * f;
    o.a10 = 300.0f  - 3.0f*f; o.a11 = 3000.0f + 5.0f*f*f - 2.0f*f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.a0 + in.a4 + in.a8, in.a1 + in.a5 + in.a9,
                  in.a2 + in.a6 + in.a10, in.a3 + in.a7 + in.a11);
}
