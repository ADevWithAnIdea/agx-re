#include <metal_stdlib>
using namespace metal;
// OPT-08: can Apple9 directly write a varying/output (fragment color output / render target)
// whose slot is selected dynamically per lane? MSL has no array-typed fragment-output syntax
// (EXP-0111 FS-11, re-confirmed structurally below by f_reject not being dispatched -- its
// non-existence as valid MSL is the FS-11 finding, not repeated here); the only expressible
// lowering is branch-unrolled, compile-time-fixed [[color(n)]] outputs. FS-11 found its 2-target
// version compiles to a SINGLE frag_color_store instruction despite two logically distinct
// per-RT writes -- flagged UNKNOWN, not bit-decoded. This file reproduces that 2-target shape
// FRESH (f_main2) for a byte-level re-derivation, and extends to a genuinely 3-way divergent
// selector (f_main3) to see whether the single-store shape holds, or whether store count scales
// with target count (distinguishing "narrow 2-target compiler coincidence" from "a real
// hardware indirect-target mechanism").
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}

struct FOut2 { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
fragment FOut2 f_main2(float4 pos [[position]]) {
    uint idx = (uint)pos.x & 1u;   // genuinely per-fragment divergent, not uniform
    FOut2 o;
    o.c0 = float4(0,0,0,0);
    o.c1 = float4(0,0,0,0);
    if (idx == 0u) { o.c0 = float4(1,0,0,1); }
    else           { o.c1 = float4(0,1,0,1); }
    return o;
}

struct FOut3 { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; float4 c2 [[color(2)]]; };
fragment FOut3 f_main3(float4 pos [[position]]) {
    uint idx = (uint)pos.x % 3u;   // genuinely per-fragment divergent, 3-way
    FOut3 o;
    o.c0 = float4(0,0,0,0);
    o.c1 = float4(0,0,0,0);
    o.c2 = float4(0,0,0,0);
    if      (idx == 0u) { o.c0 = float4(1,0,0,1); }
    else if (idx == 1u) { o.c1 = float4(0,1,0,1); }
    else                { o.c2 = float4(0,0,1,1); }
    return o;
}
