#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; float4 va; };
vertex VO v_a(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1.0,-1.0), float2(3.0,-1.0), float2(-1.0,3.0) };
    VO o; o.pos = float4(p[vid],0.0,1.0);
    o.va = float4(float(vid)*0.25, 0.5, 0.75, 1.0);
    return o;
}
fragment float4 f_a(VO in [[stage_in]]) { return in.va; }
