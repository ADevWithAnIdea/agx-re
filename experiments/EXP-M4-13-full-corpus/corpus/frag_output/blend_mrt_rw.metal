#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// programmable blend across TWO targets: read+modify both color(0) and color(1)
struct MRT2 { half4 c0 [[color(0)]]; half4 c1 [[color(1)]]; };
fragment MRT2 fMain(VOut in [[stage_in]], MRT2 dst) {
    MRT2 o; o.c0 = max(dst.c0, half4(in.col)); o.c1 = min(dst.c1, half4(in.col.wzyx)); return o;
}
