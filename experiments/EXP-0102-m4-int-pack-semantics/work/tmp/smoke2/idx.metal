#include <metal_stdlib>
using namespace metal;
kernel void k(device float *out [[buffer(0)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = unpack_unorm2x16_to_float(gid | (gid<<16)).x;
}
