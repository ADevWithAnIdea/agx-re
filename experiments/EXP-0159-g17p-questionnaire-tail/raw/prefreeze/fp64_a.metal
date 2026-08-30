#include <metal_stdlib>
using namespace metal;
kernel void k(device double* out [[buffer(0)]], device const double* a [[buffer(1)]]) {
  out[0] = a[0] + a[1];
}
