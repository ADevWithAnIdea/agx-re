#include <metal_stdlib>
using namespace metal;
kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v = a[tid];
    float x1 = v + 10.0f;
    float x2 = -1.0f;
    if (a[tid+1] > 0.5f) {
        x2 = v + a[tid+2] + 20.0f;
    }
    out[tid*2+0] = x1;
    out[tid*2+1] = x2;
}
