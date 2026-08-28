#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; float4 va; };
static float2 tri(uint vid) { return float2((vid==2)?3.0:-1.0, (vid==1)?3.0:-1.0); }
vertex VO v_a(uint vid [[vertex_id]]) {
    VO o; o.pos = float4(tri(vid),0.0,1.0);
    o.va = float4(vid==0?0.90:0.10, vid==1?0.90:0.10, vid==2?0.90:0.10, 1.0);
    return o;
}
fragment float4 f_a(VO in [[stage_in]]) { return in.va; }
