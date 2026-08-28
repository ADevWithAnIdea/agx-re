#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device float *out     [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    float x = a[gid];
    out[gid] = precise::sin(x) + fast::exp(x) + fast::log(x) + rint(x) + sqrt(x);
}
