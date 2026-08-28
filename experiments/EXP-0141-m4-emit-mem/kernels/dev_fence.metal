// EXP-0141 device-fence carrier. OWN MSL.
// atomic_thread_fence(mem_device, seq_cst) around a divergent device-atomic
// region -- the shape db.json attributes to `mem_fence` (6 B, 07 04 54 84 0a 00).
// A threadgroup_barrier(mem_device) before the final read makes the observable
// DETERMINISTIC (every lane's atomic has retired), so the whole-kernel output is
// a host-computable oracle rather than a race.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o          [[buffer(0)]],
              device const uint* a    [[buffer(1)]],
              device atomic_uint* c   [[buffer(2)]],
              uint tid [[thread_position_in_grid]])
{
    uint v = a[tid];
    o[tid] = v + 1u;
    atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst);
    if (v > 3u) {
        atomic_fetch_add_explicit(c, v, memory_order_relaxed);
    } else {
        atomic_fetch_or_explicit(c, 0x10000u, memory_order_relaxed);
    }
    atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst);
    threadgroup_barrier(mem_flags::mem_device);
    o[tid] = atomic_load_explicit(c, memory_order_relaxed) + v;
}
