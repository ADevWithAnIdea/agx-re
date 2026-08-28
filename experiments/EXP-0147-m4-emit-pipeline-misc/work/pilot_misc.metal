#include <metal_stdlib>
using namespace metal;
static float2 tri(uint vid){ return float2((vid==2)?3.0:-1.0,(vid==1)?3.0:-1.0); }
struct VO { float4 pos [[position]]; float4 va; };
vertex VO v_a(uint vid [[vertex_id]]) {
    VO o; o.pos=float4(tri(vid),0.0,1.0);
    o.va=float4(vid==0?0.90:0.10, vid==1?0.90:0.10, vid==2?0.90:0.10, 1.0); return o;
}
// raster-order-group carrier
struct ROS { device float4 *acc [[buffer(1), raster_order_group(0)]]; };
fragment float4 f_ros(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]],
                      device float4 *acc [[buffer(1), raster_order_group(0)]]) {
    float4 v = acc[0] + dst*2.0 + src;
    acc[0] = v;
    return v;
}
// sample-read carrier (MSAA)
fragment float4 f_samp(VO in [[stage_in]], uint sid [[sample_id]], constant float4 &src [[buffer(0)]]) {
    return in.va * float(sid+1) + src;
}
