#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device uint *out      [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    float x = a[gid];
    out[gid] = uint(rint(x)) + uint(floor(x)) + uint(ceil(x)) + uint(trunc(x)) + uint(round(x));
}
