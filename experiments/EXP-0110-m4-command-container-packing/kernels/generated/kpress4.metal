#include <metal_stdlib>
using namespace metal;
kernel void kpress4(device float *out [[buffer(0)]], device float *in [[buffer(1)]], uint i [[thread_position_in_grid]]) {
  float a[4];
  a[0] = in[i] + 0.0;
  a[1] = in[i] + 1.0;
  a[2] = in[i] + 2.0;
  a[3] = in[i] + 3.0;
  a[0] = a[0] * a[(1)%4] + a[(2)%4];
  a[1] = a[1] * a[(2)%4] + a[(3)%4];
  a[2] = a[2] * a[(3)%4] + a[(4)%4];
  a[3] = a[3] * a[(4)%4] + a[(5)%4];
  a[0] = a[0] * a[(1)%4] + a[(2)%4];
  a[1] = a[1] * a[(2)%4] + a[(3)%4];
  a[2] = a[2] * a[(3)%4] + a[(4)%4];
  a[3] = a[3] * a[(4)%4] + a[(5)%4];
  float s = 0.0;
  s += a[0];
  s += a[1];
  s += a[2];
  s += a[3];
  out[i] = s;
}
