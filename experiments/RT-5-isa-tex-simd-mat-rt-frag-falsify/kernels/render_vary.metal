#include <metal_stdlib>
using namespace metal;

// Full-screen triangle. Two float4 varyings with distinct components:
//   vc = (0.20,0.40,0.60,0.80), vd = (0.10,0.30,0.50,0.70) at screen centre.
// (a tiny position term prevents constant-folding to a flat load.)
// Fragment returns vc, so pixel = vc. Splicing an iter's varying-slot byte
// should swap which varying/component the output channel reads.
struct VOut {
    float4 pos [[position]];
    float4 vc;
    float4 vd;
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o;
    o.pos = float4(p[vid], 0, 1);
    float k = 0.02f * p[vid].x;
    o.vc = float4(0.20f, 0.40f, 0.60f, 0.80f) + float4(k, k, k, 0);
    o.vd = float4(0.10f, 0.30f, 0.50f, 0.70f) + float4(k, k, k, 0);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return in.vc;
}
