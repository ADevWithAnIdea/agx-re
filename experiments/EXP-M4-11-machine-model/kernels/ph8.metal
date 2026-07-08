#include <metal_stdlib>
using namespace metal;
kernel void k(device half* out [[buffer(0)]],
              device const half* in [[buffer(1)]],
              constant uint& n [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  half a0 = in[gid*8+0];
  half a1 = in[gid*8+1];
  half a2 = in[gid*8+2];
  half a3 = in[gid*8+3];
  half a4 = in[gid*8+4];
  half a5 = in[gid*8+5];
  half a6 = in[gid*8+6];
  half a7 = in[gid*8+7];
  for (uint i=1;i<n;i++) {
    half t = in[i];
    a0 = fma(a0, t, a1);
    a1 = fma(a1, t, a2);
    a2 = fma(a2, t, a3);
    a3 = fma(a3, t, a4);
    a4 = fma(a4, t, a5);
    a5 = fma(a5, t, a6);
    a6 = fma(a6, t, a7);
    a7 = fma(a7, t, a0);
  }
  out[gid*8+0] = a0;
  out[gid*8+1] = a1;
  out[gid*8+2] = a2;
  out[gid*8+3] = a3;
  out[gid*8+4] = a4;
  out[gid*8+5] = a5;
  out[gid*8+6] = a6;
  out[gid*8+7] = a7;
}
