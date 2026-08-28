#include <metal_stdlib>
using namespace metal;
kernel void shuffle_static(device int* out [[buffer(0)]],
                            uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = simd_shuffle(v, (ushort)5);
}
kernel void shufflexor_static(device int* out [[buffer(0)]],
                            uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = simd_shuffle_xor(v, (ushort)1);
}
kernel void quadshuffle_static(device int* out [[buffer(0)]],
                            uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = quad_shuffle(v, (ushort)1);
}
