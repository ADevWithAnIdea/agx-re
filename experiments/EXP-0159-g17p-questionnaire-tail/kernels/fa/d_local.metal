#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]]) {
  double x = (double)a[0]; double y = (double)a[1]; o[0] = (float)(x + y); }
