#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* a   [[buffer(1)]],
              device float* b   [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    bfloat x0 = bfloat(a[tid]);
    bfloat x1 = bfloat(b[tid]);
    bfloat x2 = bfloat(a[tid+1u]);
    bfloat x3 = bfloat(b[tid+1u]);
    bfloat s  = x0 + x1;
    out[tid]      = float(s);
    out[tid+1u]   = float(x2 + x3);
}
