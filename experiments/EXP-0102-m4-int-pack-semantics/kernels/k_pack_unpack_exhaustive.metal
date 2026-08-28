#include <metal_stdlib>
using namespace metal;

kernel void unpacksn_exh(device float *out [[buffer(0)]],
                          uint gid [[thread_position_in_grid]]) {
    uint u = gid | (gid << 16);
    out[gid] = unpack_snorm2x16_to_float(u).x;
}

kernel void unpackun_exh(device float *out [[buffer(0)]],
                          uint gid [[thread_position_in_grid]]) {
    uint u = gid | (gid << 16);
    out[gid] = unpack_unorm2x16_to_float(u).x;
}
