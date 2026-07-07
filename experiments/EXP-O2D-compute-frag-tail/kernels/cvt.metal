#include <metal_stdlib>
using namespace metal;
kernel void f2h(device half* o [[buffer(0)]], device const float* a [[buffer(1)]], uint i [[thread_position_in_grid]]) { o[i] = half(a[i]); }
kernel void h2f(device float* o [[buffer(0)]], device const half* a [[buffer(1)]], uint i [[thread_position_in_grid]]) { o[i] = float(a[i]); }
