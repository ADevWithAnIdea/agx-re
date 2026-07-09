#include <metal_stdlib>
using namespace metal;
kernel void k_umin(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]], device const uint* b [[buffer(2)]], uint g [[thread_position_in_grid]]) { out[g] = min(a[g], b[g]); }
