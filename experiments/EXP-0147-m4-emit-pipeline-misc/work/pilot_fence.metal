#include <metal_stdlib>
using namespace metal;
__attribute__((noinline)) static float slow(device const float *a, uint i) {
    float s = 0.0; for (uint k=0;k<4;k++) s += a[(i+k)&63] * float(k+1); return s;
}
kernel void k_call(device float *out [[buffer(0)]], device const float *a [[buffer(1)]],
                   uint tid [[thread_position_in_grid]]) {
    out[tid] = slow(a, tid) + a[tid];
}
kernel void k_cf(device float *out [[buffer(0)]], device const float *a [[buffer(1)]],
                 uint tid [[thread_position_in_grid]]) {
    float s = 0.0;
    for (uint k=0;k<8;k++) { if (a[k] < 0.0) continue; if (a[k] > 100.0) break; s += a[k]*float(k+1); }
    out[tid] = s + a[tid];
}
kernel void k_tgfence(device float *out [[buffer(0)]], device const float *a [[buffer(1)]],
                      threadgroup float *sh [[threadgroup(0)]],
                      uint tid [[thread_position_in_threadgroup]], uint gid [[thread_position_in_grid]]) {
    sh[tid] = a[gid]*2.0;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float s = sh[(tid+1)&31] + sh[(tid+2)&31];
    threadgroup_barrier(mem_flags::mem_device);
    out[gid] = s + a[gid];
}
kernel void k_atomic(device atomic_uint *ac [[buffer(2)]], device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]], uint tid [[thread_position_in_grid]]) {
    uint v = atomic_fetch_add_explicit(ac, 1u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_device | mem_flags::mem_texture);
    out[tid] = a[tid] + float(v&7);
}
