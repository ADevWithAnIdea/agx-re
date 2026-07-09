#include <metal_stdlib>
using namespace metal;
struct QuadTessHalf { half edge[4]; half inside[2]; };
kernel void kMain(device QuadTessHalf* out [[buffer(0)]],
                  const device float4* corners [[buffer(1)]],
                  uint pid [[thread_position_in_grid]]) {
    float4 e = corners[pid];
    QuadTessHalf q;
    q.edge[0]=half(e.x); q.edge[1]=half(e.y); q.edge[2]=half(e.z); q.edge[3]=half(e.w);
    q.inside[0]=half(max(e.x,e.z)); q.inside[1]=half(max(e.y,e.w));
    out[pid]=q;
}
