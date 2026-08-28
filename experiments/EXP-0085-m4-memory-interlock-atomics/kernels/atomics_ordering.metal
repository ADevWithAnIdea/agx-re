// EXP-0085 — ordering-tag exposure probe for ATOM-07 groundwork (deferred
// item; this file records only whether the *language* accepts a non-relaxed
// memory_order on a device atomic RMW in this MSL build -- NOT the native
// fence/barrier encoding, which is out of scope for this increment).
// Isolated in its own translation unit so a rejection here (informative
// negative result) cannot poison compilation of the main atomics.metal file.
#include <metal_stdlib>
using namespace metal;

kernel void da_add_relaxed(device atomic_uint* target [[buffer(0)]],
                            device uint* deltas [[buffer(1)]],
                            device uint* old_out [[buffer(2)]],
                            device uint* idx [[buffer(3)]],
                            uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_add_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_add_seqcst(device atomic_uint* target [[buffer(0)]],
                           device uint* deltas [[buffer(1)]],
                           device uint* old_out [[buffer(2)]],
                           device uint* idx [[buffer(3)]],
                           uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_add_explicit(&target[idx[tid]], deltas[tid], memory_order_seq_cst);
}

kernel void da_add_acqrel(device atomic_uint* target [[buffer(0)]],
                           device uint* deltas [[buffer(1)]],
                           device uint* old_out [[buffer(2)]],
                           device uint* idx [[buffer(3)]],
                           uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_add_explicit(&target[idx[tid]], deltas[tid], memory_order_acq_rel);
}
