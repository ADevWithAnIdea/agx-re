#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device float *out      [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    float v = a[gid];
    out[gid] = v * v + 3.0f;
}
