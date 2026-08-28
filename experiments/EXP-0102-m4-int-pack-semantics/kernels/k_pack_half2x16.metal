#include <metal_stdlib>
using namespace metal;

kernel void packh(device const float2 *a [[buffer(0)]],
                   device uint *out [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    half2 h = half2(a[gid]);
    out[gid] = as_type<uint>(h);
}

kernel void unpackh(device const uint *a [[buffer(0)]],
                     device float2 *out [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    half2 h = as_type<half2>(a[gid]);
    out[gid] = float2(h);
}
