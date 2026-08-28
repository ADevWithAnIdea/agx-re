#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    uint p = a[tid];
    float2 v1 = unpack_unorm2x16_to_float(p);
    float x1 = v1.x + v1.y;
    float2 v2 = unpack_snorm2x16_to_float(p);
    float x2 = v2.x + v2.y + 5.0f;
    out[tid*2+0] = x1;
    out[tid*2+1] = x2;
}
