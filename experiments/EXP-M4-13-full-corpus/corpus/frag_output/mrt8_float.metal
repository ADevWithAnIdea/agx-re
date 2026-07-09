#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// 8 render targets (max MRT) -> many parallel color stores
struct MRT8 { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; float4 c2 [[color(2)]]; float4 c3 [[color(3)]];
              float4 c4 [[color(4)]]; float4 c5 [[color(5)]]; float4 c6 [[color(6)]]; float4 c7 [[color(7)]]; };
fragment MRT8 fMain(VOut in [[stage_in]]) {
    MRT8 o; float4 b = in.col;
    o.c0=b; o.c1=b*2; o.c2=b*3; o.c3=b*4; o.c4=b+in.uv.xyxy; o.c5=b-in.uv.yxyx; o.c6=fract(b*7); o.c7=abs(b-0.5);
    return o;
}
