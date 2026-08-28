#include <metal_stdlib>
using namespace metal;
// FS-11: the only MSL-expressible way to make a fragment OUTPUT's destination depend on
// a value is to branch-unroll over individually-named, compile-time-fixed [[color(n)]]
// outputs. Each of the 2 render targets is written by its own dedicated branch arm.
// `idx` is derived from [[position]] (px&1), i.e. genuinely PER-FRAGMENT DIVERGENT --
// NOT a uniform draw-wide value -- so the compiler cannot resolve which RT to target in
// the once-per-draw constant/uniform program; it must handle it per-invocation. Oracle:
// even-x columns -> RT0=red, odd-x columns -> RT1=green (both RTs otherwise clear).
struct FOut { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FOut f_main(float4 pos [[position]]) {
    uint idx = (uint)pos.x & 1u;
    FOut o;
    o.c0 = float4(0,0,0,0);
    o.c1 = float4(0,0,0,0);
    if (idx == 0u) {
        o.c0 = float4(1,0,0,1);
    } else {
        o.c1 = float4(0,1,0,1);
    }
    return o;
}
