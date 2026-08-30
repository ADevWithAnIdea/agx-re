// k_tilerw2.metal -- EXP-0163 tile read + MRT together.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// The adversarial cross of k_mrt3 and k_tileread: TWO render targets, both read
// AND written, so frag_tile_setup must emit both access modes AND more than one
// selector value in the same program.  This is the arm where a per-RT selector
// and an access-mode selector are simultaneously live.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
    float  v1;
    float  v2;
    float  v3;
};

struct FOut {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
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

fragment FOut f_main(VOut in [[stage_in]],
                     float4 d0 [[color(0)]],
                     float4 d1 [[color(1)]])
{
    FOut o;
    o.c0 = float4(d0.x * 8.0f + in.v0, d1.y * 16.0f + in.v1, in.v2, in.v3);
    o.c1 = float4(d1.x * 8.0f + in.v1, d0.y * 16.0f + in.v2, in.v3, in.v0);
    return o;
}
