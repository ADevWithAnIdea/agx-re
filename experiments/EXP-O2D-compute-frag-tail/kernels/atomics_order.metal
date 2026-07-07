#include <metal_stdlib>
using namespace metal;

// ============ Sub-experiment 1: atomic memory-ordering + fence bits ============
// NOTE (compile probe): Metal REJECTS memory_order_seq_cst/acquire/release/acq_rel
// on atomic_fetch_*_explicit RMW ops (only memory_order_relaxed compiles) -> ordering
// is NOT carried on the 0x67 RMW op. Ordering/scope live in atomic_thread_fence (0x07).

// --- RMW: only relaxed is legal ---
kernel void at_add_relaxed(device atomic_uint* a [[buffer(0)]],
                           device const uint* v [[buffer(1)]],
                           uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(a, v[i], memory_order_relaxed);
}

// --- atomic_thread_fence: vary flags. Order fixed to seq_cst (see fence_orders below). ---
// A device store then a cross-lane device load brackets the fence so it is not DCE'd.
kernel void fence_none(device uint* g [[buffer(0)]],
                       device uint* o [[buffer(2)]],
                       uint i [[thread_position_in_grid]],
                       uint n [[threads_per_grid]]) {
    g[i] = i;
    atomic_thread_fence(mem_none, memory_order_seq_cst);
    o[i] = g[(i + 1) % n];
}
kernel void fence_device(device uint* g [[buffer(0)]],
                         device uint* o [[buffer(2)]],
                         uint i [[thread_position_in_grid]],
                         uint n [[threads_per_grid]]) {
    g[i] = i;
    atomic_thread_fence(mem_device, memory_order_seq_cst);
    o[i] = g[(i + 1) % n];
}
kernel void fence_tg(device uint* o [[buffer(2)]],
                     threadgroup uint* s [[threadgroup(0)]],
                     uint i [[thread_position_in_grid]],
                     uint li [[thread_position_in_threadgroup]],
                     uint tl [[threads_per_threadgroup]]) {
    s[li] = li;
    atomic_thread_fence(mem_threadgroup, memory_order_seq_cst);
    o[i] = s[(li + 1) % tl];
}
kernel void fence_dev_tg(device uint* g [[buffer(0)]],
                         device uint* o [[buffer(2)]],
                         threadgroup uint* s [[threadgroup(0)]],
                         uint i [[thread_position_in_grid]],
                         uint li [[thread_position_in_threadgroup]],
                         uint tl [[threads_per_threadgroup]]) {
    g[i] = i; s[li] = li;
    atomic_thread_fence(mem_device | mem_threadgroup, memory_order_seq_cst);
    o[i] = g[(i + 1) % tl] + s[(li + 1) % tl];
}
kernel void fence_texture(device uint* g [[buffer(0)]],
                          device uint* o [[buffer(2)]],
                          uint i [[thread_position_in_grid]],
                          uint n [[threads_per_grid]]) {
    g[i] = i;
    atomic_thread_fence(mem_texture, memory_order_seq_cst);
    o[i] = g[(i + 1) % n];
}

// --- scope-qualified fences (Metal 3 thread_scope) ---
kernel void fence_scope_dev(device uint* g [[buffer(0)]],
                            device uint* o [[buffer(2)]],
                            uint i [[thread_position_in_grid]],
                            uint n [[threads_per_grid]]) {
    g[i] = i;
    atomic_thread_fence(mem_device, memory_order_seq_cst, thread_scope_device);
    o[i] = g[(i + 1) % n];
}
kernel void fence_scope_tg(device uint* g [[buffer(0)]],
                           device uint* o [[buffer(2)]],
                           uint i [[thread_position_in_grid]],
                           uint n [[threads_per_grid]]) {
    g[i] = i;
    atomic_thread_fence(mem_device, memory_order_seq_cst, thread_scope_threadgroup);
    o[i] = g[(i + 1) % n];
}
kernel void fence_scope_simd(device uint* g [[buffer(0)]],
                             device uint* o [[buffer(2)]],
                             uint i [[thread_position_in_grid]],
                             uint n [[threads_per_grid]]) {
    g[i] = i;
    atomic_thread_fence(mem_device, memory_order_seq_cst, thread_scope_simdgroup);
    o[i] = g[(i + 1) % n];
}
