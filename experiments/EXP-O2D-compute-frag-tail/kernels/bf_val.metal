#include <metal_stdlib>
using namespace metal;
// bfloat add via float I/O so the HW testbed (float32 buffers) can drive it.
// Splice the 0x11-group opsel (byte+2 0x1c->0x1d) to prove add->mul on HW.
kernel void bfadd(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    bfloat x = bfloat(a[i]);
    bfloat y = bfloat(b[i]);
    o[i] = float(x + y);
}
