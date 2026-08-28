#include <metal_stdlib>
using namespace metal;
kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v = a[tid];
    float x1 = v + 10.0f;
    float f0 = a[tid+1] + 0.01f;
    float f1 = a[tid+2] + 0.02f;
    float f2 = a[tid+3] + 0.03f;
    float f3 = a[tid+4] + 0.04f;
    float x2 = v + 20.0f;
    out[tid*4+0] = x1;
    out[tid*4+1] = x2;
    out[tid*4+2] = f0+f1;
    out[tid*4+3] = f2+f3;
}
