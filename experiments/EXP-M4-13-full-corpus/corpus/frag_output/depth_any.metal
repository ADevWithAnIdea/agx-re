#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// [[depth(any)]] shader-computed depth export
struct FO { float4 c [[color(0)]]; float d [[depth(any)]]; };
fragment FO fMain(VOut in [[stage_in]]) { FO o; o.c=in.col; o.d=saturate(in.uv.x*in.uv.y); return o; }
