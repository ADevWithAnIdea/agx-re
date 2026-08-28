#include <metal_stdlib>
using namespace metal;
// Control for tgdiv2_dev.metal: NO barrier at all (source-level weak control).
kernel void k(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
              device uint *scratch [[buffer(2)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    uint d = a[gid];
    uint iters = (lid + 1u) * 32u;
    for (uint i = 0u; i < iters; i++) { d = d * 1664525u + 1013904223u; }
    scratch[lid] = d;
    // NO barrier
    out[gid] = scratch[255u - lid];
}
