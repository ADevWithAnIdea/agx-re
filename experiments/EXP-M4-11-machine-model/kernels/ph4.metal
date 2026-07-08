#include <metal_stdlib>
using namespace metal;
kernel void k(device half* out [[buffer(0)]],
              device const half* in [[buffer(1)]],
              constant uint& n [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  half a0 = in[gid*4+0];
  half a1 = in[gid*4+1];
  half a2 = in[gid*4+2];
  half a3 = in[gid*4+3];
  for (uint i=1;i<n;i++) {
    half t = in[i];
    a0 = fma(a0, t, a1);
    a1 = fma(a1, t, a2);
    a2 = fma(a2, t, a3);
    a3 = fma(a3, t, a0);
  }
  out[gid*4+0] = a0;
  out[gid*4+1] = a1;
  out[gid*4+2] = a2;
  out[gid*4+3] = a3;
}
