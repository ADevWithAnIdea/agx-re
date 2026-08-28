#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* a   [[buffer(1)]],
              device float* b   [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    bfloat x0 = bfloat(a[0]);
    bfloat x1 = bfloat(a[1]);
    bfloat x2 = bfloat(a[2]);
    bfloat x3 = bfloat(a[3]);
    bfloat s  = x0 + x1;
    out[0] = float(s);
    out[1] = float(x2);
    out[2] = float(x3);
    out[3] = float(b[0]);
}
