#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    threadgroup int tile[64];
    tile[lid] = a[gid];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint j = (lid + 1) & 63;
    out[gid] = tile[j];
}
