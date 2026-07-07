#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device const float *c [[buffer(2)]],
              device const float *d [[buffer(3)]],
              device float *out [[buffer(4)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid] + c[gid] + d[gid];
}
