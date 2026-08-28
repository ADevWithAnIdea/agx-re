#include <metal_stdlib>
using namespace metal;

kernel void h2add(device const half2 *a [[buffer(0)]],
                   device const half2 *b [[buffer(1)]],
                   device half2 *out [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

kernel void h2mul(device const half2 *a [[buffer(0)]],
                   device const half2 *b [[buffer(1)]],
                   device half2 *out [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid];
}

kernel void h2fma(device const half2 *a [[buffer(0)]],
                   device const half2 *b [[buffer(1)]],
                   device const half2 *c [[buffer(2)]],
                   device half2 *out [[buffer(3)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = fma(a[gid], b[gid], c[gid]);
}
