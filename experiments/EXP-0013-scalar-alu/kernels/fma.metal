#include <metal_stdlib>
using namespace metal;

kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device const float *c [[buffer(2)]],
              device float *out [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = fma(a[gid], b[gid], c[gid]);
}
