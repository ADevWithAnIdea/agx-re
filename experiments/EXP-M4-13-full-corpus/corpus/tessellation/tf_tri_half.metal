#include <metal_stdlib>
using namespace metal;
struct TriTessHalf { half edge[3]; half inside; };
kernel void kMain(device TriTessHalf* out [[buffer(0)]],
                  const device float4* ctrl [[buffer(1)]],
                  constant float& base [[buffer(2)]],
                  uint pid [[thread_position_in_grid]]) {
    float3 e = float3(base) + ctrl[pid].xyz;
    TriTessHalf t;
    t.edge[0] = half(e.x); t.edge[1] = half(e.y); t.edge[2] = half(e.z);
    t.inside = half((e.x+e.y+e.z)*(1.0/3.0));
    out[pid] = t;
}
