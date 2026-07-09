#include <metal_stdlib>
using namespace metal;
kernel void k_fmax(device float* out [[buffer(0)]], device const float* a [[buffer(1)]], device const float* b [[buffer(2)]], uint g [[thread_position_in_grid]]) { out[g] = max(a[g], b[g]); }
