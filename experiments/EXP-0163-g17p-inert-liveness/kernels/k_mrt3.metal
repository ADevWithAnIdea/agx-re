// k_mrt3.metal -- EXP-0163 MULTIPLE-RENDER-TARGET carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  db.json documents frag_tile_setup.sel as a per-render-target selector
// that "steps 0x0c -> 0x30 -> 0xc0 across RT0/RT1/RT2", and frag_color_store's
// byte+4 flags as "0x00 in every plain store; 0x08 appears in the MRT /
// array-slice variant".  EXP-0155 swept frag_tile_setup.sel and
// frag_color_store.store_mode on SINGLE-render-target carriers only, where there
// is exactly one target to select and nothing for a selector to move to.
// imageblock_store.b4 sits at the same byte offset (+4) as frag_color_store's
// flags, so the same argument applies to it.
//
// Three RTs with mutually distinct values: mis-selecting a target sends a store
// to the wrong attachment, which the harness sees because it reads back ALL
// THREE (PIX0/PIX1/PIX2).
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
    float4 c2 [[color(2)]];
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

fragment FOut f_main(VOut in [[stage_in]])
{
    FOut o;
    o.c0 = float4(in.v0, in.v1, in.v2, in.v3);
    o.c1 = float4(in.v1 + 5000.0f, in.v2, in.v3, in.v0);
    o.c2 = float4(in.v2 + 90000.0f, in.v3, in.v0, in.v1);
    return o;
}
