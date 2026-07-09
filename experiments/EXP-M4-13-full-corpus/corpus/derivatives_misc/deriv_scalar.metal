#include <metal_stdlib>
using namespace metal;
// Isolate scalar screen-space derivatives dfdx/dfdy on a single float.
// AGX implements these via quad-lane differencing; expect a dedicated
// derivative/quad-shuffle opcode distinct from ordinary fsub.
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) {
    float f  = in.uv.x * in.uv.y;
    float gx = dfdx(f);
    float gy = dfdy(f);
    return float4(gx, gy, gx + gy, 1.0);
}
