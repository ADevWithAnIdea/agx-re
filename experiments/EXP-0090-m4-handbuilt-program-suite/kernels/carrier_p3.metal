#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device const float* a [[buffer(1)]],
              device const int* n [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = a[tid];
    int count = n[tid];
    for (int i = 0; i < count; i++) {
        acc = acc + 1.5;
    }
    float r;
    if (acc > 100.0) {
        r = acc * 2.0;
    } else {
        r = acc - 3.0;
    }
    out[tid] = r;
}
