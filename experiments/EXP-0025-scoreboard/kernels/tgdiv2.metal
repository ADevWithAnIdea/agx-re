#include <metal_stdlib>
using namespace metal;
// Live variable-length delay: scratch[lid] stores the LCG result (loop cannot be eliminated).
// lid 255 runs 8192 iters (slowest writer); lid 0 runs 32 iters (fastest) and reads scratch[255].
kernel void k(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[256];
    uint d = a[gid];
    uint iters = (lid + 1u) * 32u;
    for (uint i=0;i<iters;i++){ d = d*1664525u + 1013904223u; }
    scratch[lid] = d;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[gid] = scratch[255 - lid];
}
