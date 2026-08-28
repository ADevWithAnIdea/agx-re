#include <metal_stdlib>
using namespace metal;
// FS-07 compile_scan target: dfdx() applied to a float4, algebraically independent
// components. Hypothesis: exactly 4 derivative ops, axis=dfdx (0x92) only.
struct VOut { float4 pos [[position]]; float2 uv [[user(locn0)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float4 v = float4(sin(in.uv.x*3.7), cos(in.uv.y*2.1),
                       sin(in.uv.x*1.3 + in.uv.y*5.9), cos(in.uv.x*0.7 - in.uv.y*4.4));
    float4 d = dfdx(v);
    return d;
}
