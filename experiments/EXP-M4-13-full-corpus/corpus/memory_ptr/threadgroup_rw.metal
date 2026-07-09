#include <metal_stdlib>
using namespace metal;
// threadgroup (local) memory store + barrier + neighbor load.
kernel void k(device float* out [[buffer(0)]],
              device const float* in [[buffer(1)]],
              uint gid [[thread_position_in_grid]],
              uint lid [[thread_position_in_threadgroup]],
              uint tgsz [[threads_per_threadgroup]]) {
    threadgroup float scratch[256];
    scratch[lid] = in[gid];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint nb = (lid + 1u) % tgsz;
    out[gid] = scratch[nb] + scratch[lid];
}
