#include <metal_stdlib>
using namespace metal;
// Variable-length per-lane delay: lid 0 finishes fast and reads scratch[255] (written by lid 255,
// the SLOWEST writer). WITHOUT a barrier, the fast reader sees stale/zero tgmem.
kernel void k(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[256];
    uint v = a[gid];
    uint d = v + 1u;
    uint iters = (lid + 1u) * 64u;
    for (uint i=0;i<iters;i++){ d = d*1664525u + 1013904223u; }
    scratch[lid] = v + (d & 0u);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[gid] = scratch[255 - lid];
}
