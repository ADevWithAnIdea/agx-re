#include <metal_stdlib>
using namespace metal;
kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v = a[tid];
    float x1 = v + 10.0f;
    float x2 = v + 20.0f;
    float x3 = v + 30.0f;
    out[tid*3+0] = x1;
    out[tid*3+1] = x2;
    out[tid*3+2] = x3;
}
