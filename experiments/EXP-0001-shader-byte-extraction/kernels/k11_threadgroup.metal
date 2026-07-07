#include <metal_stdlib>
using namespace metal;

// Threadgroup (shared) memory round-trip with a barrier. Exercises
// threadgroup-memory store/load + barrier instruction encodings.
kernel void k(device const float *a [[buffer(0)]],
              device float *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]],
              uint lid [[thread_position_in_threadgroup]]) {
    threadgroup float scratch[64];
    scratch[lid] = a[gid];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[gid] = scratch[(lid + 1) & 63];
}
