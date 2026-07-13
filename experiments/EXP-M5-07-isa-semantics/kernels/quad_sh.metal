#include <metal_stdlib>
using namespace metal;
kernel void k(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    uint v = a[gid];
    out[gid] = quad_shuffle_xor(v, 1u);
}
