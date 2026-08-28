#include <metal_stdlib>
using namespace metal;
kernel void ktex0_samp0(device float *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  float acc = 0.0;
  out[i] = acc;
}
