#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* a [[buffer(1)]],
              device int* n [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid+0] = a[tid];
    out[tid+1] = float(n[tid]);
}
