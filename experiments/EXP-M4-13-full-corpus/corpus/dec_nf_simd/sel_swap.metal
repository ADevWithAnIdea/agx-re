#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* a [[buffer(1)]],
              device const float* b [[buffer(2)]], device const uint* c [[buffer(3)]],
              uint i [[thread_position_in_grid]]) { out[i] = select(b[i], a[i], c[i] != 0u); }
