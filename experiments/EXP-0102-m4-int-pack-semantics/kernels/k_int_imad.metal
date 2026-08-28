#include <metal_stdlib>
using namespace metal;

kernel void imadu(device const uint *a [[buffer(0)]],
                   device const uint *b [[buffer(1)]],
                   device const uint *c [[buffer(2)]],
                   device uint *out [[buffer(3)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid] + c[gid];
}

kernel void imads(device const int *a [[buffer(0)]],
                   device const int *b [[buffer(1)]],
                   device const int *c [[buffer(2)]],
                   device int *out [[buffer(3)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid] + c[gid];
}
