#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device float *out      [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    float v = a[gid];
    float t = (float)gid;
    t = t*1.5f + 2.0f; t = t*t - 1.0f; t = t*0.5f + 4.0f; t = t*t + t;
    out[gid] = v + t;   // v (loaded) consumed only at the very end
}
