#include <metal_stdlib>
using namespace metal;
// Vector-width (float4) derivatives: dfdx/dfdy applied component-wise.
// Tests whether the derivative op is vectorized or scalarized per lane.
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) {
    float4 v = float4(in.uv, in.uv.x*in.uv.y, in.uv.x+in.uv.y);
    return dfdx(v) + dfdy(v);
}
