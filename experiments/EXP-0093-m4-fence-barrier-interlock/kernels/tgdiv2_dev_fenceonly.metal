#include <metal_stdlib>
using namespace metal;
// ATOM-10 reverse-direction control: same per-lane variable-delay device-memory
// race as tgdiv2_dev.metal, but uses a standalone atomic_thread_fence(mem_device)
// instead of threadgroup_barrier(mem_device) -- MSL does not claim this provides
// execution convergence, so this is expected to race like the no-barrier control
// (source-level negative baseline). Splicing its compiled fence byte+3 0x84->0x85
// (adding the bit ATOM-10's forward direction proved removes convergence) tests
// whether that bit alone is SUFFICIENT to add convergence to an otherwise
// fence-only op, symmetric to the forward-direction splice.
kernel void k(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
              device uint *scratch [[buffer(2)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    uint d = a[gid];
    uint iters = (lid + 1u) * 32u;
    for (uint i = 0u; i < iters; i++) { d = d * 1664525u + 1013904223u; }
    scratch[lid] = d;
    atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device);
    out[gid] = scratch[255u - lid];
}
