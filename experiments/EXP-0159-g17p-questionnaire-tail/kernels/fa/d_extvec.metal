#include <metal_stdlib>
using namespace metal;
typedef double dbl2 __attribute__((ext_vector_type(2)));
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]]) {
  dbl2 v = { (double)a[0], (double)a[1] }; o[0] = (float)(v.x + v.y); }
