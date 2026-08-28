#include <metal_stdlib>
using namespace metal;

kernel void packu4x8(device const float4 *a [[buffer(0)]],
                      device uint *out [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = pack_float_to_unorm4x8(a[gid]);
}

kernel void unpacku4x8(device const uint *a [[buffer(0)]],
                        device float4 *out [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    out[gid] = unpack_unorm4x8_to_float(a[gid]);
}
