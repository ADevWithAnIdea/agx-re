#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]]) {
  double2 v = double2(a[0], a[1]); o[0] = (float)(v.x * v.y); }
