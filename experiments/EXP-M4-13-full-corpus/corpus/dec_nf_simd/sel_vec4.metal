#include <metal_stdlib>
using namespace metal;
kernel void k(device float4* out [[buffer(0)]],
              device const float4* a [[buffer(1)]],
              device const float4* b [[buffer(2)]],
              device const uint4* c [[buffer(3)]],
              uint i [[thread_position_in_grid]]) {
    out[i] = select(a[i], b[i], c[i] != uint4(0));
}
