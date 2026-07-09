#include <metal_stdlib>
using namespace metal;
// Half-precision derivatives + fwidth on half2. Probes whether AGX has a
// 16-bit derivative form or promotes to fp32 for the quad difference.
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment half4 fMain(VOut in [[stage_in]]) {
    half2 h  = half2(in.uv * in.uv.yx);
    half2 gx = dfdx(h);
    half2 gy = dfdy(h);
    half2 w  = fwidth(h);
    return half4(gx, gy + w);
}
