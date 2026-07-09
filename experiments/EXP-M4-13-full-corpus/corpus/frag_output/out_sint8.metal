#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// int4 -> RGBA8Sint: signed narrowing/clamp pack
fragment int4 fMain(VOut in [[stage_in]]) {
    int4 v = int4(in.col * 300.0 - 150.0); return v ^ int4(int(in.uv.x*7));
}
