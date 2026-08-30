// EXP-0141 threadgroup-atomic splice carrier. OWN MSL.
// o[2] is the integrity sentinel (see atomic_dev.metal).
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o          [[buffer(0)]],
              device const uint* a    [[buffer(1)]],
              uint tid [[thread_position_in_grid]],
              uint li  [[thread_position_in_threadgroup]])
{
    if (li == 0) o[2] = 0xA5A5A5A5u;
    threadgroup atomic_uint c;
    if (li == 0) atomic_store_explicit(&c, 0u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint v0 = a[li];
    uint v1 = a[li + 8];
    atomic_fetch_add_explicit(&c, v0, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (li == 0) { o[0] = atomic_load_explicit(&c, memory_order_relaxed); o[1] = v1; }
}
