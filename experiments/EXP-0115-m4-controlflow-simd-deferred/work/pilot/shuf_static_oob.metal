#include <metal_stdlib>
using namespace metal;
kernel void shuffle_static_oob(device int* out [[buffer(0)]],
                            uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = simd_shuffle(v, (ushort)40);
}
kernel void quadshuffle_static_oob(device int* out [[buffer(0)]],
                            uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = quad_shuffle(v, (ushort)7);
}
