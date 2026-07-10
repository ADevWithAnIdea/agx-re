#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device float *out     [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid] = a[tid] + b[tid];
}
