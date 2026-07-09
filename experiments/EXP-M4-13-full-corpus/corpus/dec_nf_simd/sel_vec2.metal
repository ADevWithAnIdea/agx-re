#include <metal_stdlib>
using namespace metal;
kernel void k(device float2* out [[buffer(0)]], device const float2* a [[buffer(1)]],
              device const float2* b [[buffer(2)]], device const uint2* c [[buffer(3)]],
              uint i [[thread_position_in_grid]]) { out[i] = select(a[i], b[i], c[i] != uint2(0)); }
