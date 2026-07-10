#include <metal_stdlib>
using namespace metal;

vertex float4 v(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid], 0, 1);
}

// Read front-facing flag into the colour output. Front-facing -> white, back -> black.
fragment float4 f(bool ff [[front_facing]]) {
    return ff ? float4(1.0, 1.0, 1.0, 1.0) : float4(0.0, 0.0, 0.0, 1.0);
}
