#include <metal_stdlib>
using namespace metal;

vertex float4 v(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid], 0, 1);
}

// Literal sample-id / barycentric preamble reads (the exact builtins the rule
// comment names as the byte0==0x04 residue producers).
fragment float4 f(uint sid [[sample_id]],
                  float3 bary [[barycentric_coord]]) {
    return float4(float(sid) * 0.25, bary.x, bary.y, bary.z);
}
