#include <metal_stdlib>
using namespace metal;
// fwidth = abs(dfdx)+abs(dfdy) at scalar and vector width. Isolates the
// abs source-modifier folded onto the derivative result and the add.
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) {
    float  f = sin(in.uv.x) * cos(in.uv.y);
    float2 v = in.uv * 2.0;
    float  wf = fwidth(f);
    float2 wv = fwidth(v);
    return float4(wf, wv, wf + wv.x);
}
