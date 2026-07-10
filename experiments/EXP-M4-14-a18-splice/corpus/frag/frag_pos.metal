#include <metal_stdlib>
using namespace metal;

vertex float4 v(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid], 0, 1);
}

// Read the interpolated fragment position and write it to the colour output.
// pos.xy are window coords (pixels); on a 1x1 target both are ~0.5.
fragment float4 f(float4 pos [[position]]) {
    return float4(pos.x, pos.y, pos.z, pos.w);
}
