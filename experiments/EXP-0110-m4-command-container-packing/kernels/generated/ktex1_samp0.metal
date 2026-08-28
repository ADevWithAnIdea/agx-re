#include <metal_stdlib>
using namespace metal;
kernel void ktex1_samp0(texture2d<float> t0 [[texture(0)]], device float *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  float acc = 0.0;
  acc += t0.read(uint2(0,0)).x;
  out[i] = acc;
}
