#include <metal_stdlib>
using namespace metal;
kernel void kbuf2(device float *b0 [[buffer(0)]], device float *b1 [[buffer(1)]], uint i [[thread_position_in_grid]]) {
  float acc = 0.0;
  acc += b0[i];
  acc += b1[i];
  b0[i] = acc;
}
