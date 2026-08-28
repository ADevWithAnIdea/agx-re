#include <metal_stdlib>
using namespace metal;
kernel void kbuf1(device float *b0 [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  float acc = 0.0;
  acc += b0[i];
  b0[i] = acc;
}
