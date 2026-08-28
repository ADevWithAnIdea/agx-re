#include <metal_stdlib>
using namespace metal;
static float2 tri(uint vid){ return float2((vid==2)?3.0:-1.0,(vid==1)?3.0:-1.0); }
struct VO { float4 pos [[position]]; float4 va; };
vertex VO v_a(uint vid [[vertex_id]]) {
    VO o; o.pos=float4(tri(vid),0.0,1.0);
    o.va=float4(vid==0?0.90:0.10, vid==1?0.90:0.10, vid==2?0.90:0.10, 1.0); return o;
}
struct MRT { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
fragment MRT f_mrt(float4 d0 [[color(0)]], float4 d1 [[color(1)]], constant float4 &src [[buffer(0)]]) {
    MRT o; o.c0 = d0*2.0 + src; o.c1 = d1*4.0 - src; return o;
}
fragment float4 f_sampos(VO in [[stage_in]], float2 sp [[sample_position]], constant float4 &src [[buffer(0)]]) {
    return float4(sp.x, sp.y, in.va.z, 1.0) + src;
}
fragment float4 f_persample(float4 dst [[color(0)]], uint sid [[sample_id]], constant float4 &src [[buffer(0)]]) {
    return dst * float(sid+1) + src;
}
