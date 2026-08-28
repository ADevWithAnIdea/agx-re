#include <metal_stdlib>
using namespace metal;
kernel void shuffle_dyn(device int* out [[buffer(0)]],
                         device const int* idxbuf [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    ushort idx = (ushort)idxbuf[i];
    out[i] = simd_shuffle(v, idx);
}
