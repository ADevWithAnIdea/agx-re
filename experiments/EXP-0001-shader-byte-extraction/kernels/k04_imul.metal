#include <metal_stdlib>
using namespace metal;

// int32 mul. Minimal pair with k03_iadd (only the operator differs).
kernel void k(device const int *a [[buffer(0)]],
              device const int *b [[buffer(1)]],
              device int *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid];
}
