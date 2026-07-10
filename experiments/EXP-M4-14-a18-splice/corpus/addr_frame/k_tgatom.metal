#include <metal_stdlib>
using namespace metal;
kernel void k(device const int* a [[buffer(0)]],
              device int* o [[buffer(2)]],
              uint i  [[thread_position_in_grid]],
              uint li [[thread_position_in_threadgroup]]) {
    threadgroup atomic_int acc;
    if (li == 0) atomic_store_explicit(&acc, 0, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(&acc, a[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = atomic_load_explicit(&acc, memory_order_relaxed);
}
