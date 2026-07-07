#include <metal_stdlib>
using namespace metal;
kernel void k(device const uint *a [[buffer(0)]],
              device uint *out      [[buffer(1)]],
              uint gid [[thread_position_in_grid]],
              uint lid [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[512];
    uint v = a[gid];
    uint d = v + 1u;
    for (uint i=0;i<300u;i++){ d = d*1664525u + 1013904223u; }
    scratch[lid] = v + (d & 0u);
    // NO barrier
    out[gid] = scratch[511 - lid];
}
