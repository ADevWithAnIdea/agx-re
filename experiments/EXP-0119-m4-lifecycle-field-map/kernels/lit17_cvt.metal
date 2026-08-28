#include <metal_stdlib>
using namespace metal;
kernel void k(device int* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int v = a[tid];
    float x1 = float(v) + 10.0f;
    float x2 = float((uint)v) + 20.0f;
    out[tid*2+0] = x1;
    out[tid*2+1] = x2;
}
