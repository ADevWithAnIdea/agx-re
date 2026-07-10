#include <metal_stdlib>
using namespace metal;

// Full-screen triangle, no vertex buffer.
vertex float4 v(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid], 0, 1);
}

// Constant colour output -> the compiler emits a colour PACK + tile store.
fragment float4 f() {
    return float4(0.5, 0.25, 0.75, 1.0);
}
