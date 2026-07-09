#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// uint4 -> RGBA8Uint: unsigned narrowing/clamp pack
fragment uint4 fMain(VOut in [[stage_in]]) {
    uint4 v = uint4(in.col * 500.0); return v + uint4(uint(in.uv.y*3));
}
