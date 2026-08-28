#include <metal_stdlib>
using namespace metal;
kernel void ktex2_samp1(texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]], sampler s0 [[sampler(0)]], device float *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  float acc = 0.0;
  acc += t0.sample(s0, float2(0.5, 0.5)).x;
  acc += t1.sample(s0, float2(0.5, 0.5)).x;
  out[i] = acc;
}
