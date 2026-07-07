#include <metal_stdlib>
using namespace metal;
vertex float4 v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid], 0.0, 1.0);
}
fragment float4 f_main(uint pid [[primitive_id]]) {
    return float4(float(pid), 0, 0, 1);
}
