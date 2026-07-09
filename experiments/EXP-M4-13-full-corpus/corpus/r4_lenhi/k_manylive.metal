#include <metal_stdlib>
using namespace metal;
struct U { uint v[64]; };
kernel void k(device uint* out [[buffer(0)]], constant U& u [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    // 24 independent live accumulators, each a chain of index/address math from uniforms
    uint a[24];
    for (uint i=0;i<24;i++) a[i]=u.v[(tid+i)&63u];
    // cross-mix so all stay live simultaneously (high register pressure)
    for (uint r=0;r<3;r++)
      for (uint i=0;i<24;i++)
        a[i] = a[i]*3u + a[(i+7u)%24u] + u.v[(a[i]+r)&63u];
    for (uint i=0;i<24;i++) out[(a[i])&1023u] = a[(i*5u+1u)%24u];
}
