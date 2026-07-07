#include <metal_stdlib>
using namespace metal;

// Store a constant to buffer(0). Minimal pair with k09_write_buf1
// (same shape, different destination buffer index -> operand/binding change).
kernel void k(device float *out0 [[buffer(0)]],
              device float *out1 [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out0[gid] = 1.0f;
}
