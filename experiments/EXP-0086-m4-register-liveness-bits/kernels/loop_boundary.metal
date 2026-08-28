#include <metal_stdlib>
using namespace metal;
kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v = a[tid];
    float x1 = v + 10.0f;
    float acc = 0.0f;
    uint n = (uint)a[tid+1];
    for (uint i = 0; i < n; i++) {
        acc = acc + a[tid+2+i] + v;
    }
    float x2 = v + 20.0f;
    out[tid*3+0] = x1;
    out[tid*3+1] = x2;
    out[tid*3+2] = acc;
}
