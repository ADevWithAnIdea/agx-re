#include <metal_stdlib>
using namespace metal;
vertex float4 v_main(uint vid [[vertex_id]]) {
    // clockwise winding -> front-facing under Metal default (MTLWindingClockwise)
    float2 p[3] = { float2(-1,-1), float2(-1,3), float2(3,-1) };
    return float4(p[vid], 0.0, 1.0);
}
fragment float4 f_main(bool ff [[front_facing]]) {
    return float4(ff ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}
