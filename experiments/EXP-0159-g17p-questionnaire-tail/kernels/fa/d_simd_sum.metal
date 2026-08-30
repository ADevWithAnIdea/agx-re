#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
  o[t] = (float)simd_sum((double)a[t]); }
