#include <metal_stdlib>
using namespace metal;

// b - a. Minimal pair with k12_fsub_ab (operands swapped).
kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device float *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = b[gid] - a[gid];
}
