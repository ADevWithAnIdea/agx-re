#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    o.col = float4(p[vid].x, p[vid].y, 0.25, 0.75);
    o.uv  = 0.5*p[vid] + 0.5; return o;
}
// dual-source blend outputs: color(0) index(0) and index(1)
struct FO { half4 s0 [[color(0), index(0)]]; half4 s1 [[color(0), index(1)]]; };
fragment FO fMain(VOut in [[stage_in]]) { FO o; o.s0=half4(in.col); o.s1=half4(in.col.a); return o; }
