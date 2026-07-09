#include <metal_stdlib>
using namespace metal;
struct QuadTessHalf { half edge[4]; half inside[2]; };
kernel void kMain(device QuadTessHalf* out [[buffer(0)]],
                  const device float4* centers [[buffer(1)]],
                  constant float3& eye [[buffer(2)]],
                  constant float2& lodParams [[buffer(3)]],
                  uint pid [[thread_position_in_grid]]) {
    float3 c = centers[pid].xyz;
    float d = distance(c, eye);
    float lod = clamp(lodParams.x / max(d, 1e-3), 1.0, lodParams.y);
    float f = exp2(floor(log2(lod)));   // snap to pow2
    half hf = half(f);
    QuadTessHalf q;
    q.edge[0]=hf; q.edge[1]=hf; q.edge[2]=hf; q.edge[3]=hf;
    q.inside[0]=hf; q.inside[1]=hf;
    out[pid]=q;
}
