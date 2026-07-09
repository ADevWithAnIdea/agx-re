#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float v [[user(locn0)]]; };
vertex VOut vMain(uint vid [[vertex_id]], device const float* a [[buffer(0)]]){
    VOut o; o.pos = float4(a[vid], a[vid+1u], 0.0, 1.0); o.v = a[vid+2u]; return o;
}
fragment float4 fMain(VOut in [[stage_in]]){
    float v = in.v;
    float b = quad_broadcast(v, 0);
    float su = quad_sum(v);
    float mx = quad_max(v);
    bool first = quad_is_first();
    bool helper = simd_is_helper_thread();
    return float4(b, su, mx, (first?1.0:0.0) + (helper?2.0:0.0));
}
