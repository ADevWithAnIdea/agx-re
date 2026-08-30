#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]]) {
  o[0] = static_cast<float>(static_cast<double>(a[0]) / static_cast<double>(a[1])); }
