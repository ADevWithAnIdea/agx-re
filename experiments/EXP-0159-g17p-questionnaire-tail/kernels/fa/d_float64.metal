#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]]) {
  _Float64 x = (_Float64)a[0]; o[0] = (float)(x + x); }
