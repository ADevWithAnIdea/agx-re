// EXP-0085 — authored MSL, atomic operation set (ATOM-01..06).
// Clean-room: OWN-SHADER. All source here is authored by us for this experiment.
//
// Uniform harness contract per kernel (see harness/atomics_probe.m):
//   buffer(0) target   — the atomic location(s). One element for "uniform"
//                         addressing cases (every lane hits the same slot,
//                         triggering Apple's SIMD-reduce path per EXP-0018);
//                         N elements for "indexed" addressing cases (every
//                         lane hits its own slot at idx[tid], defeating the
//                         reduce path).
//   buffer(1) deltas   — per-lane input operand, asymmetric (tid-derived).
//   buffer(2) old_out  — per-lane value returned by the atomic op (pre-op
//                         value for RMW forms; success flag + observed old
//                         for compare-exchange, see cmpxchg kernels).
//   buffer(3) idx      — per-lane target index. All-zero for uniform cases;
//                         idx[tid] = tid for indexed cases. Also reused as
//                         the "new" tag value source for exchange/cmpxchg
//                         permutation probes (buffer(4) below).
//   buffer(4) tag      — per-lane distinct tag value (tid + 1), used by the
//                         exchange/cmpxchg permutation-invariant kernels so
//                         analysis.py can reconstruct a linearizable history
//                         without relying on run-to-run return ORDER (which
//                         may legitimately vary; see PRE_REGISTRATION.md).
//
// Every kernel body is a single atomic call immediately after reading its
// operands — no extra ALU between operand computation and the atomic, and no
// extra ALU between the atomic and writing old_out, so the op itself (not
// scheduling) is what's under test structurally as well as functionally.

#include <metal_stdlib>
using namespace metal;

// ---- 32-bit integer RMW, device scope --------------------------------
kernel void da_add(device atomic_uint* target [[buffer(0)]],
                    device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_add_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_sub(device atomic_uint* target [[buffer(0)]],
                    device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_sub_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_and(device atomic_uint* target [[buffer(0)]],
                    device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_and_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_or(device atomic_uint* target [[buffer(0)]],
                   device uint* deltas [[buffer(1)]],
                   device uint* old_out [[buffer(2)]],
                   device uint* idx [[buffer(3)]],
                   uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_or_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_xor(device atomic_uint* target [[buffer(0)]],
                    device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_xor_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_umin(device atomic_uint* target [[buffer(0)]],
                     device uint* deltas [[buffer(1)]],
                     device uint* old_out [[buffer(2)]],
                     device uint* idx [[buffer(3)]],
                     uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_min_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_umax(device atomic_uint* target [[buffer(0)]],
                     device uint* deltas [[buffer(1)]],
                     device uint* old_out [[buffer(2)]],
                     device uint* idx [[buffer(3)]],
                     uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_max_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_smin(device atomic_int* target [[buffer(0)]],
                     device int* deltas [[buffer(1)]],
                     device int* old_out [[buffer(2)]],
                     device uint* idx [[buffer(3)]],
                     uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_min_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

kernel void da_smax(device atomic_int* target [[buffer(0)]],
                     device int* deltas [[buffer(1)]],
                     device int* old_out [[buffer(2)]],
                     device uint* idx [[buffer(3)]],
                     uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_max_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

// float fetch_add — the only float atomic MSL exposes (EXP-0018).
kernel void da_fadd(device atomic_float* target [[buffer(0)]],
                     device float* deltas [[buffer(1)]],
                     device float* old_out [[buffer(2)]],
                     device uint* idx [[buffer(3)]],
                     uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_add_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
}

// exchange (=store-with-return) — permutation-invariant probe: each lane
// exchanges in its own unique tag value and records the old value it saw.
kernel void da_exch(device atomic_uint* target [[buffer(0)]],
                     device uint* deltas [[buffer(1)]],
                     device uint* old_out [[buffer(2)]],
                     device uint* idx [[buffer(3)]],
                     device uint* tag [[buffer(4)]],
                     uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_exchange_explicit(&target[idx[tid]], tag[tid], memory_order_relaxed);
}

// no-return-value use of exchange: same op, MSL return value discarded.
// Compares tokenized bytes against da_exch to test whether an unused return
// changes the compiled encoding (ATOM item: return-value vs no-return forms).
kernel void da_exch_noret(device atomic_uint* target [[buffer(0)]],
                           device uint* deltas [[buffer(1)]],
                           device uint* old_out [[buffer(2)]],
                           device uint* idx [[buffer(3)]],
                           device uint* tag [[buffer(4)]],
                           uint tid [[thread_position_in_grid]]) {
    atomic_exchange_explicit(&target[idx[tid]], tag[tid], memory_order_relaxed);
    old_out[tid] = deltas[tid]; // unrelated write so the kernel still has an observable side effect
}

// atomic_store — MSL's explicit no-return form (distinct call, same family?).
kernel void da_store(device atomic_uint* target [[buffer(0)]],
                      device uint* deltas [[buffer(1)]],
                      device uint* old_out [[buffer(2)]],
                      device uint* idx [[buffer(3)]],
                      device uint* tag [[buffer(4)]],
                      uint tid [[thread_position_in_grid]]) {
    atomic_store_explicit(&target[idx[tid]], tag[tid], memory_order_relaxed);
    old_out[tid] = deltas[tid];
}

// compare_exchange_weak — single-winner invariant probe. Every lane attempts
// CAS(expected=0, desired=tag[tid]) on the same slot; deterministic result:
// exactly one lane succeeds, every failing lane observes the *current*
// (winner's) value, never a torn/partial value.
kernel void da_cmpxchg(device atomic_uint* target [[buffer(0)]],
                        device uint* deltas [[buffer(1)]],
                        device uint* old_out [[buffer(2)]],
                        device uint* idx [[buffer(3)]],
                        device uint* tag [[buffer(4)]],
                        device uint* success_out [[buffer(5)]],
                        uint tid [[thread_position_in_grid]]) {
    uint expected = 0;
    bool ok = atomic_compare_exchange_weak_explicit(&target[idx[tid]], &expected, tag[tid],
                                                      memory_order_relaxed, memory_order_relaxed);
    old_out[tid] = expected;   // MSL sets *expected to the observed current value on failure
    success_out[tid] = ok ? 1u : 0u;
}

// ---- STATIC-literal-address variants (true compile-time-provable uniform
// address, buffer(3) idx ignored) — ATOM-05 SIMD-pre-combine probe. Unlike
// da_add/da_exch/... above (which read idx[tid] from a buffer, so the
// address is only RUNTIME-uniform, not statically provable), these access
// target[0] as a literal constant index, matching EXP-0018's da_add_r/
// atomicuse methodology exactly. Comparing the tokenized instruction stream
// of these against the idx[]-driven kernels of the same op isolates whether
// Apple's SIMD pre-combine optimization keys on static provable uniformity
// specifically (see PROGRESS.md build log / RESULTS.md ATOM-05/06).
kernel void da_add_static0(device atomic_uint* target [[buffer(0)]],
                            device uint* deltas [[buffer(1)]],
                            device uint* old_out [[buffer(2)]],
                            device uint* idx [[buffer(3)]],
                            uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_add_explicit(&target[0], deltas[tid], memory_order_relaxed);
}

kernel void da_xor_static0(device atomic_uint* target [[buffer(0)]],
                            device uint* deltas [[buffer(1)]],
                            device uint* old_out [[buffer(2)]],
                            device uint* idx [[buffer(3)]],
                            uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_xor_explicit(&target[0], deltas[tid], memory_order_relaxed);
}

kernel void da_umin_static0(device atomic_uint* target [[buffer(0)]],
                             device uint* deltas [[buffer(1)]],
                             device uint* old_out [[buffer(2)]],
                             device uint* idx [[buffer(3)]],
                             uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_fetch_min_explicit(&target[0], deltas[tid], memory_order_relaxed);
}

kernel void da_exch_static0(device atomic_uint* target [[buffer(0)]],
                             device uint* deltas [[buffer(1)]],
                             device uint* old_out [[buffer(2)]],
                             device uint* idx [[buffer(3)]],
                             device uint* tag [[buffer(4)]],
                             uint tid [[thread_position_in_grid]]) {
    old_out[tid] = atomic_exchange_explicit(&target[0], tag[tid], memory_order_relaxed);
}

kernel void da_cmpxchg_static0(device atomic_uint* target [[buffer(0)]],
                                device uint* deltas [[buffer(1)]],
                                device uint* old_out [[buffer(2)]],
                                device uint* idx [[buffer(3)]],
                                device uint* tag [[buffer(4)]],
                                device uint* success_out [[buffer(5)]],
                                uint tid [[thread_position_in_grid]]) {
    uint expected = 0;
    bool ok = atomic_compare_exchange_weak_explicit(&target[0], &expected, tag[tid],
                                                      memory_order_relaxed, memory_order_relaxed);
    old_out[tid] = expected;
    success_out[tid] = ok ? 1u : 0u;
}

// ---- 32-bit integer RMW, threadgroup scope ----------------------------
// One threadgroup only (dispatch grid == threadgroup size), target lives in
// threadgroup memory, initialized by lane 0, barrier before/after so the
// dispatch-wide readback (copied to device out[]) is race-free with the
// atomics under test — only the atomic RMW itself is unsynchronized across
// lanes, which is exactly what's being probed.
kernel void ta_add(device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    device atomic_uint* result [[buffer(6)]],
                    uint tid [[thread_position_in_grid]],
                    uint ltid [[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint tgtarget[256];
    if (ltid == 0) {
        for (uint i = 0; i < 256; i++) atomic_store_explicit(&tgtarget[i], 0u, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    old_out[tid] = atomic_fetch_add_explicit(&tgtarget[idx[tid]], deltas[tid], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (ltid < 256) atomic_store_explicit(&result[ltid], atomic_load_explicit(&tgtarget[ltid], memory_order_relaxed), memory_order_relaxed);
}

kernel void ta_sub(device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    device atomic_uint* result [[buffer(6)]],
                    uint tid [[thread_position_in_grid]],
                    uint ltid [[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint tgtarget[256];
    if (ltid == 0) {
        for (uint i = 0; i < 256; i++) atomic_store_explicit(&tgtarget[i], 1000000u, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    old_out[tid] = atomic_fetch_sub_explicit(&tgtarget[idx[tid]], deltas[tid], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (ltid < 256) atomic_store_explicit(&result[ltid], atomic_load_explicit(&tgtarget[ltid], memory_order_relaxed), memory_order_relaxed);
}

kernel void ta_min(device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    device atomic_uint* result [[buffer(6)]],
                    uint tid [[thread_position_in_grid]],
                    uint ltid [[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint tgtarget[256];
    if (ltid == 0) {
        for (uint i = 0; i < 256; i++) atomic_store_explicit(&tgtarget[i], 0xffffffffu, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    old_out[tid] = atomic_fetch_min_explicit(&tgtarget[idx[tid]], deltas[tid], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (ltid < 256) atomic_store_explicit(&result[ltid], atomic_load_explicit(&tgtarget[ltid], memory_order_relaxed), memory_order_relaxed);
}

kernel void ta_max(device uint* deltas [[buffer(1)]],
                    device uint* old_out [[buffer(2)]],
                    device uint* idx [[buffer(3)]],
                    device atomic_uint* result [[buffer(6)]],
                    uint tid [[thread_position_in_grid]],
                    uint ltid [[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint tgtarget[256];
    if (ltid == 0) {
        for (uint i = 0; i < 256; i++) atomic_store_explicit(&tgtarget[i], 0u, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    old_out[tid] = atomic_fetch_max_explicit(&tgtarget[idx[tid]], deltas[tid], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (ltid < 256) atomic_store_explicit(&result[ltid], atomic_load_explicit(&tgtarget[ltid], memory_order_relaxed), memory_order_relaxed);
}

kernel void ta_exch(device uint* deltas [[buffer(1)]],
                     device uint* old_out [[buffer(2)]],
                     device uint* idx [[buffer(3)]],
                     device uint* tag [[buffer(4)]],
                     device atomic_uint* result [[buffer(6)]],
                     uint tid [[thread_position_in_grid]],
                     uint ltid [[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint tgtarget[256];
    if (ltid == 0) {
        for (uint i = 0; i < 256; i++) atomic_store_explicit(&tgtarget[i], 0xdeadbeefu, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    old_out[tid] = atomic_exchange_explicit(&tgtarget[idx[tid]], tag[tid], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (ltid < 256) atomic_store_explicit(&result[ltid], atomic_load_explicit(&tgtarget[ltid], memory_order_relaxed), memory_order_relaxed);
}

kernel void ta_cmpxchg(device uint* deltas [[buffer(1)]],
                        device uint* old_out [[buffer(2)]],
                        device uint* idx [[buffer(3)]],
                        device uint* tag [[buffer(4)]],
                        device uint* success_out [[buffer(5)]],
                        device atomic_uint* result [[buffer(6)]],
                        uint tid [[thread_position_in_grid]],
                        uint ltid [[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint tgtarget[256];
    if (ltid == 0) {
        for (uint i = 0; i < 256; i++) atomic_store_explicit(&tgtarget[i], 0u, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint expected = 0;
    bool ok = atomic_compare_exchange_weak_explicit(&tgtarget[idx[tid]], &expected, tag[tid],
                                                      memory_order_relaxed, memory_order_relaxed);
    old_out[tid] = expected;
    success_out[tid] = ok ? 1u : 0u;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (ltid < 256) atomic_store_explicit(&result[ltid], atomic_load_explicit(&tgtarget[ltid], memory_order_relaxed), memory_order_relaxed);
}

// ---- 64-bit atomics: min/max only, and only in the VOID (no-return) form --
// Re-validated in this experiment (see PROGRESS.md build log): MSL rejects
// atomic_fetch_min_explicit/atomic_fetch_max_explicit/atomic_fetch_add_explicit
// AND atomic_load_explicit on atomic_ulong (device or threadgroup). Only the
// non-fetching atomic_min_explicit/atomic_max_explicit (void return) compile.
// This sharpens EXP-0018's "only the void 64-bit atomic_min/max form exists"
// into a hard ATOM item finding: 64-bit RMW has NO return-value form at all
// in the tested MSL surface, so old_out cannot be populated by the atomic
// itself; it is left at its poison fill (0xEE...) and excluded from the
// per-lane invariant (only the post-dispatch final target value is checked,
// via non-atomic CPU-side readback after GPU completion).
kernel void da_umin64(device atomic_ulong* target [[buffer(0)]],
                       device ulong* deltas [[buffer(1)]],
                       device ulong* old_out [[buffer(2)]],
                       device uint* idx [[buffer(3)]],
                       uint tid [[thread_position_in_grid]]) {
    atomic_min_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
    old_out[tid] = 0; // no native return; zeroed so the record is well-defined (see note above)
}

kernel void da_umax64(device atomic_ulong* target [[buffer(0)]],
                       device ulong* deltas [[buffer(1)]],
                       device ulong* old_out [[buffer(2)]],
                       device uint* idx [[buffer(3)]],
                       uint tid [[thread_position_in_grid]]) {
    atomic_max_explicit(&target[idx[tid]], deltas[tid], memory_order_relaxed);
    old_out[tid] = 0;
}
