#include <metal_stdlib>
using namespace metal;
kernel void k_tgrw(device float* out [[buffer(0)]], device const float* in [[buffer(1)]],
                   uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]],
                   uint tgsz [[threads_per_threadgroup]]) {
    threadgroup float scratch[256];
    scratch[lid] = in[gid];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint nb = (lid + 1u) % tgsz;
    out[gid] = scratch[nb] + scratch[lid];
}
kernel void k_sgrp(device uint* o [[buffer(0)]], device const uint* a [[buffer(1)]], uint i [[thread_position_in_grid]]) {
    uint v = a[i];
    o[i]      = simd_sum(v);
    o[i + 1u] = simd_product(v);
}
