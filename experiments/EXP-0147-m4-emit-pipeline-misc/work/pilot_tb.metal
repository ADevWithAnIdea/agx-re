#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 vc; };
vertex VOut v_full(uint vid [[vertex_id]], constant float4 &vp [[buffer(0)]]) {
    float2 pos[3] = { float2(-1.0,-1.0), float2(3.0,-1.0), float2(-1.0,3.0) };
    VOut o; o.pos = float4(pos[vid], 0.0, 1.0); o.vc = vp * float(vid+1); return o;
}
fragment float4 f_tb(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]]) {
    return dst * 2.0 + src;
}
struct MRT { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
fragment MRT f_mrt(float4 d0 [[color(0)]], float4 d1 [[color(1)]], constant float4 &src [[buffer(0)]]) {
    MRT o; o.c0 = d0*2.0 + src; o.c1 = d1*4.0 - src; return o;
}
fragment float4 f_vary(VOut in [[stage_in]]) { return in.vc; }
