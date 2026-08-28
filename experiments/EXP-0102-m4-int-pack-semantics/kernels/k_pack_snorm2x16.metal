#include <metal_stdlib>
using namespace metal;

kernel void packsn(device const float2 *a [[buffer(0)]],
                    device uint *out [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = pack_float_to_snorm2x16(a[gid]);
}

kernel void unpacksn(device const uint *a [[buffer(0)]],
                      device float2 *out [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = unpack_snorm2x16_to_float(a[gid]);
}
