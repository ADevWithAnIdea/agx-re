#include <metal_stdlib>
using namespace metal;
// Writers are delayed by a data-dependent LCG chain so their scratch stores land late.
// Readers (in another simdgroup) read scratch[511-lid]. WITH the barrier this is correct
// (out[lid]=511-lid); WITHOUT it, readers see stale/zero tgmem -> silent corruption.
kernel void k(device const uint *a [[buffer(0)]],
              device uint *out      [[buffer(1)]],
              uint gid [[thread_position_in_grid]],
              uint lid [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[512];
    uint v = a[gid];
    uint d = v + 1u;
    for (uint i=0;i<300u;i++){ d = d*1664525u + 1013904223u; }
    scratch[lid] = v + (d & 0u);          // stores v (d&0==0); store waits on the chain
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[gid] = scratch[511 - lid];
}
