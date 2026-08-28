#include <metal_stdlib>
using namespace metal;

kernel void packu4x8_manual(device const uint *a [[buffer(0)]],
                             device const uint *b [[buffer(1)]],
                             device const uint *c [[buffer(2)]],
                             device const uint *d [[buffer(3)]],
                             device uint *out [[buffer(4)]],
                             uint gid [[thread_position_in_grid]]) {
    uint r = (a[gid] & 0xFFu) | ((b[gid] & 0xFFu) << 8) |
             ((c[gid] & 0xFFu) << 16) | ((d[gid] & 0xFFu) << 24);
    out[gid] = r;
}
