#include <metal_stdlib>
using namespace metal;
// FS-07 compile_scan target: dfdx() applied to a float2 whose components are
// algebraically independent (distinct transcendental functions of distinct base
// varyings, so the compiler cannot fuse/reuse one component's quad-difference for
// another). Hypothesis: exactly 2 derivative ops, axis=dfdx (0x92) only.
struct VOut { float4 pos [[position]]; float2 uv [[user(locn0)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float2 v = float2(sin(in.uv.x*3.7), cos(in.uv.y*2.1));
    float2 d = dfdx(v);
    return float4(d, 0.0, 1.0);
}
