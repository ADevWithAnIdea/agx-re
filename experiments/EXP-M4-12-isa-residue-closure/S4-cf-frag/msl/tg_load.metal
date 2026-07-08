#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]], uint li[[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint c;
    if (li==0) atomic_store_explicit(&c, 0u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(&c, a[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = atomic_load_explicit(&c, memory_order_relaxed);
}
