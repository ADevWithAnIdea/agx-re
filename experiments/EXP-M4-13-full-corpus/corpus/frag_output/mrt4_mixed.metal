#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// 4 render targets, DIFFERENT output types/formats -> 4 distinct store encodings
struct MRT { float4 c0 [[color(0)]]; half4 c1 [[color(1)]]; uint4 c2 [[color(2)]]; int4 c3 [[color(3)]]; };
fragment MRT fMain(VOut in [[stage_in]]) {
    MRT o;
    o.c0 = saturate(in.col);
    o.c1 = half4(in.col.wzyx);
    o.c2 = uint4(in.col * 1000.0);
    o.c3 = int4(in.col * 200.0 - 100.0);
    return o;
}
