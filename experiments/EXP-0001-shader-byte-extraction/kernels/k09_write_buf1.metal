#include <metal_stdlib>
using namespace metal;

// Store a constant to buffer(1). Minimal pair with k08_write_buf0.
kernel void k(device float *out0 [[buffer(0)]],
              device float *out1 [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out1[gid] = 1.0f;
}
