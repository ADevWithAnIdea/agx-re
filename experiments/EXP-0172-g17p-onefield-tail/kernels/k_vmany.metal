// k_vmany.metal -- EXP-0163 WIDE-VARYING carrier (16 scalar varyings, i.e.
// slots past the 8 the single EXP-0155 carrier used).  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  vary_store.{hint2, hint6, b7} were swept on ONE carrier,
// `vary_store@c_iter/vert106` -- a vertex program with four scalar varyings plus
// [[position]], i.e. slots 0..7, a single data source (all four computed in
// registers) and a single component width.  db.json says byte+2 (hint2)
// "carries the same 0x54/0x55/0x56 data-source mode as the device_store amode",
// and out_slot spills into byte+5 bit0 only "for slots 8..15" -- so the wide
// case is where the slot/addressing tail has something to say.
//
// Sixteen mutually non-affine varyings force slots 4..19, i.e. the byte+5 bit0
// wrap AND the highest slot indices the hardware will take from a traditional
// vertex stage.  The fragment stage sums them with distinct prime weights, so
// ANY single slot landing wrong changes the sum.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  a0; float a1; float a2; float a3;
    float  a4; float a5; float a6; float a7;
    float  a8; float a9; float a10; float a11;
    float  a12; float a13; float a14; float a15;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.a0  = 1.0f + f;          o.a1  = 10.0f + f * f;
    o.a2  = 100.0f - 3.0f * f; o.a3  = 1000.0f + 5.0f * f;
    o.a4  = 2.0f - f;          o.a5  = 20.0f + 7.0f * f * f;
    o.a6  = 200.0f + 11.0f * f;o.a7  = 2000.0f - 13.0f * f;
    o.a8  = 3.0f + 17.0f * f;  o.a9  = 30.0f - 19.0f * f * f;
    o.a10 = 300.0f + 23.0f * f;o.a11 = 3000.0f + 29.0f * f;
    o.a12 = 4.0f - 31.0f * f;  o.a13 = 40.0f + 37.0f * f * f;
    o.a14 = 400.0f - 41.0f * f;o.a15 = 4000.0f + 43.0f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.a0  +  2.0f * in.a1  +  3.0f * in.a2  +  5.0f * in.a3,
                  in.a4  +  7.0f * in.a5  + 11.0f * in.a6  + 13.0f * in.a7,
                  in.a8  + 17.0f * in.a9  + 19.0f * in.a10 + 23.0f * in.a11,
                  in.a12 + 29.0f * in.a13 + 31.0f * in.a14 + 37.0f * in.a15);
}
