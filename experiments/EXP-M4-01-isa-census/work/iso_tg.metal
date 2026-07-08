#include <metal_stdlib>
using namespace metal;

// Minimal threadgroup-atomic isolation kernels (OWN-SHADER).
kernel void tg_store(device uint* o[[buffer(0)]],
                     uint i[[thread_position_in_grid]],
                     uint li[[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint c;
    if (li==0) atomic_store_explicit(&c, 0u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = atomic_load_explicit(&c, memory_order_relaxed);
}

kernel void tg_add(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]],
                   uint li[[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint c;
    if (li==0) atomic_store_explicit(&c, 0u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(&c, a[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = atomic_load_explicit(&c, memory_order_relaxed);
}

kernel void tg_max(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]],
                   uint li[[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint c;
    if (li==0) atomic_store_explicit(&c, 0u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_max_explicit(&c, a[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = atomic_load_explicit(&c, memory_order_relaxed);
}
