#include <metal_stdlib>
using namespace metal;
kernel void k(
              device const float *a0 [[buffer(0)]],
              device const float *a1 [[buffer(1)]],
              device const float *a2 [[buffer(2)]],
              device const float *a3 [[buffer(3)]],
              device const float *a4 [[buffer(4)]],
              device const float *a5 [[buffer(5)]],
              device const float *a6 [[buffer(6)]],
              device const float *a7 [[buffer(7)]],
              device const float *a8 [[buffer(8)]],
              device const float *a9 [[buffer(9)]],
              device const float *a10 [[buffer(10)]],
              device const float *a11 [[buffer(11)]],
              device const float *a12 [[buffer(12)]],
              device const float *a13 [[buffer(13)]],
              device const float *a14 [[buffer(14)]],
              device const float *a15 [[buffer(15)]],
              device const float *a16 [[buffer(16)]],
              device const float *a17 [[buffer(17)]],
              device const float *a18 [[buffer(18)]],
              device const float *a19 [[buffer(19)]],
              device float *out [[buffer(20)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a0[gid]+a1[gid]+a2[gid]+a3[gid]+a4[gid]+a5[gid]+a6[gid]+a7[gid]+a8[gid]+a9[gid]+a10[gid]+a11[gid]+a12[gid]+a13[gid]+a14[gid]+a15[gid]+a16[gid]+a17[gid]+a18[gid]+a19[gid];
}
