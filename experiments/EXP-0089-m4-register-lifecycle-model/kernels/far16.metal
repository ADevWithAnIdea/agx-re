#include <metal_stdlib>
using namespace metal;
kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v = a[tid];
    float x1 = v + 10.0f;
    float f0 = a[tid+1] + 0.0010f;
    float f1 = a[tid+2] + 0.0020f;
    float f2 = a[tid+3] + 0.0030f;
    float f3 = a[tid+4] + 0.0040f;
    float f4 = a[tid+5] + 0.0050f;
    float f5 = a[tid+6] + 0.0060f;
    float f6 = a[tid+7] + 0.0070f;
    float f7 = a[tid+8] + 0.0080f;
    float f8 = a[tid+9] + 0.0090f;
    float f9 = a[tid+10] + 0.0100f;
    float f10 = a[tid+11] + 0.0110f;
    float f11 = a[tid+12] + 0.0120f;
    float f12 = a[tid+13] + 0.0130f;
    float f13 = a[tid+14] + 0.0140f;
    float f14 = a[tid+15] + 0.0150f;
    float f15 = a[tid+16] + 0.0160f;
    float x2 = v + 20.0f;
    float sum = f0 + f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9 + f10 + f11 + f12 + f13 + f14 + f15;
    out[tid*3+0] = x1;
    out[tid*3+1] = x2;
    out[tid*3+2] = sum;
}
