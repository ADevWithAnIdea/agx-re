#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device float *out      [[buffer(1)]],
              uint gid [[thread_position_in_grid]],
              uint lid [[thread_position_in_threadgroup]]) {
    threadgroup float scratch[64];
    scratch[lid] = a[gid];
    // NO barrier -- racy
    out[gid] = scratch[63 - lid];
}
