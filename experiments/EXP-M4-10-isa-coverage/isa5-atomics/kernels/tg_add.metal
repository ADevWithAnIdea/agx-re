#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* v [[buffer(1)]],
              uint i [[thread_position_in_grid]],
              uint li [[thread_position_in_threadgroup]]) {
    threadgroup atomic_int s;
    if (li==0) atomic_store_explicit(&s, 0, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(&s, v[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (li==0) out[0] = atomic_load_explicit(&s, memory_order_relaxed);
}
