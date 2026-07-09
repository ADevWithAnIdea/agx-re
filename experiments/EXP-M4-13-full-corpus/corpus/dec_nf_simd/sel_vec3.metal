#include <metal_stdlib>
using namespace metal;
kernel void k(device float3* out [[buffer(0)]], device const float3* a [[buffer(1)]],
              device const float3* b [[buffer(2)]], device const uint3* c [[buffer(3)]],
              uint i [[thread_position_in_grid]]) { out[i] = select(a[i], b[i], c[i] != uint3(0)); }
