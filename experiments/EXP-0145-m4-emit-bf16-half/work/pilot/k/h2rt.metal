#include <metal_stdlib>
using namespace metal;
kernel void k(device float2* out [[buffer(0)]], device const float2* a [[buffer(1)]], uint g [[thread_position_in_grid]]){ half2 h=half2(a[g]); out[g]=float2(h); }
