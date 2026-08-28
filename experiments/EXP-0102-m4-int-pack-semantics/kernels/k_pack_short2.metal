#include <metal_stdlib>
using namespace metal;

kernel void s2add(device const short2 *a [[buffer(0)]],
                   device const short2 *b [[buffer(1)]],
                   device short2 *out [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

kernel void s2mul(device const short2 *a [[buffer(0)]],
                   device const short2 *b [[buffer(1)]],
                   device short2 *out [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid];
}

kernel void s2and(device const short2 *a [[buffer(0)]],
                   device const short2 *b [[buffer(1)]],
                   device short2 *out [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] & b[gid];
}
