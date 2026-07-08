#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device const float* in [[buffer(1)]],
              constant uint& n [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  float a0 = in[gid*16+0];
  float a1 = in[gid*16+1];
  float a2 = in[gid*16+2];
  float a3 = in[gid*16+3];
  float a4 = in[gid*16+4];
  float a5 = in[gid*16+5];
  float a6 = in[gid*16+6];
  float a7 = in[gid*16+7];
  float a8 = in[gid*16+8];
  float a9 = in[gid*16+9];
  float a10 = in[gid*16+10];
  float a11 = in[gid*16+11];
  float a12 = in[gid*16+12];
  float a13 = in[gid*16+13];
  float a14 = in[gid*16+14];
  float a15 = in[gid*16+15];
  for (uint i=1;i<n;i++) {
    float t = in[i];
    a0 = fma(a0, t, a1);
    a1 = fma(a1, t, a2);
    a2 = fma(a2, t, a3);
    a3 = fma(a3, t, a4);
    a4 = fma(a4, t, a5);
    a5 = fma(a5, t, a6);
    a6 = fma(a6, t, a7);
    a7 = fma(a7, t, a8);
    a8 = fma(a8, t, a9);
    a9 = fma(a9, t, a10);
    a10 = fma(a10, t, a11);
    a11 = fma(a11, t, a12);
    a12 = fma(a12, t, a13);
    a13 = fma(a13, t, a14);
    a14 = fma(a14, t, a15);
    a15 = fma(a15, t, a0);
  }
  out[gid*16+0] = a0;
  out[gid*16+1] = a1;
  out[gid*16+2] = a2;
  out[gid*16+3] = a3;
  out[gid*16+4] = a4;
  out[gid*16+5] = a5;
  out[gid*16+6] = a6;
  out[gid*16+7] = a7;
  out[gid*16+8] = a8;
  out[gid*16+9] = a9;
  out[gid*16+10] = a10;
  out[gid*16+11] = a11;
  out[gid*16+12] = a12;
  out[gid*16+13] = a13;
  out[gid*16+14] = a14;
  out[gid*16+15] = a15;
}
