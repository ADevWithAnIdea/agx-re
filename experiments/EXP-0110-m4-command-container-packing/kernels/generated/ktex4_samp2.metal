#include <metal_stdlib>
using namespace metal;
kernel void ktex4_samp2(texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]], texture2d<float> t2 [[texture(2)]], texture2d<float> t3 [[texture(3)]], sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]], device float *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  float acc = 0.0;
  acc += t0.sample(s0, float2(0.5, 0.5)).x;
  acc += t1.sample(s1, float2(0.5, 0.5)).x;
  acc += t2.sample(s0, float2(0.5, 0.5)).x;
  acc += t3.sample(s1, float2(0.5, 0.5)).x;
  out[i] = acc;
}
