#include <metal_stdlib>
using namespace metal;

// float mul. Minimal pair with k01_fadd (only the operator differs).
kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device float *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid];
}
