#include <metal_stdlib>
using namespace metal;
kernel void k(device ulong* out [[buffer(0)]],
              device const ulong* a [[buffer(1)]],
              device const ulong* b [[buffer(2)]],
              threadgroup int* tg [[threadgroup(0)]],
              uint tid [[thread_position_in_grid]],
              uint lid [[thread_index_in_threadgroup]]) {
    tg[lid] = (int)a[tid];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    ulong s = a[tid] + b[tid];              // 64-bit add -> carry-gen 0x32
    threadgroup_barrier(mem_flags::mem_device);
    int t = tg[(lid + 1) & 63];
    out[tid] = s + (ulong)t;
}
