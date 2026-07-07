#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------------------
// EXP-0018 atomics provocation kernels (OUR OWN MSL).
// Each kernel isolates ONE atomic operation so we can diff/tokenize the
// _agc.main bytes and localize the operation / address / data / return fields.
// Two shapes per op: "_r" captures the return value into o[i] (exposes the
// return-value register), the void form updates a shared counter (aggregate
// validation: many threads -> one location).
// ---------------------------------------------------------------------------

// ===== DEVICE (global) atomics, signed int =====
kernel void da_add_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                     device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_add_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_sub_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                     device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_sub_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_min_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                     device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_min_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_max_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                     device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_max_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_and_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                     device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_and_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_or_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                    device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_or_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_xor_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                     device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_xor_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_xchg_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                      device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_exchange_explicit(c, in[i], memory_order_relaxed);
}

// ===== DEVICE atomics, UNSIGNED int (min/max differ from signed) =====
kernel void da_umin_r(device atomic_uint* c [[buffer(0)]], device uint* in [[buffer(1)]],
                      device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_min_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_umax_r(device atomic_uint* c [[buffer(0)]], device uint* in [[buffer(1)]],
                      device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_max_explicit(c, in[i], memory_order_relaxed);
}
kernel void da_uadd_r(device atomic_uint* c [[buffer(0)]], device uint* in [[buffer(1)]],
                      device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_add_explicit(c, in[i], memory_order_relaxed);
}

// ===== DEVICE compare-exchange =====
kernel void da_cmpxchg_r(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                         device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    int expected = 0;
    bool ok = atomic_compare_exchange_weak_explicit(c, &expected, in[i],
                    memory_order_relaxed, memory_order_relaxed);
    o[i] = ok ? expected : -expected;
}

// ===== DEVICE load / store =====
kernel void da_load_r(device atomic_int* c [[buffer(0)]], device int* o [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    o[i] = atomic_load_explicit(c, memory_order_relaxed);
}
kernel void da_store(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_store_explicit(c, in[i], memory_order_relaxed);
}

// ===== DEVICE float atomics =====
kernel void da_fadd_r(device atomic_float* c [[buffer(0)]], device float* in [[buffer(1)]],
                      device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_add_explicit(c, in[i], memory_order_relaxed);
}
// NOTE: float atomic_fetch_min/max are NOT provided by MSL on this toolchain
// (_valid_fetch_min_type<device float*> unsatisfied) -> see kernels/probe_*.metal.
kernel void da_fxchg_r(device atomic_float* c [[buffer(0)]], device float* in [[buffer(1)]],
                       device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_exchange_explicit(c, in[i], memory_order_relaxed);
}

// ===== DEVICE 64-bit atomics =====
// NOTE: 64-bit atomic_fetch_add is NOT provided by MSL (see probe_add64.metal).
// Only the void 64-bit min/max form (§6.15.4.6) exists:
kernel void da_max64(device atomic_ulong* c [[buffer(0)]], device uint* in [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_max_explicit(c, ulong(in[i]), memory_order_relaxed);
}

// ===== DEVICE indexed atomic (address = base + index?) =====
kernel void da_add_idx(device atomic_int* c [[buffer(0)]], device int* in [[buffer(1)]],
                       device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = atomic_fetch_add_explicit(&c[i], in[i], memory_order_relaxed);
}

// ===== THREADGROUP (local) atomics =====
kernel void ta_add_r(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                     threadgroup atomic_int* t [[threadgroup(0)]],
                     uint i [[thread_position_in_grid]],
                     uint li [[thread_position_in_threadgroup]]) {
    if (li == 0) atomic_store_explicit(t, 0, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    int prev = atomic_fetch_add_explicit(t, in[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = prev + atomic_load_explicit(t, memory_order_relaxed);
}
kernel void ta_max_r(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                     threadgroup atomic_int* t [[threadgroup(0)]],
                     uint i [[thread_position_in_grid]],
                     uint li [[thread_position_in_threadgroup]]) {
    if (li == 0) atomic_store_explicit(t, -2147483647, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_max_explicit(t, in[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = atomic_load_explicit(t, memory_order_relaxed);
}
kernel void ta_xchg_r(device int* in [[buffer(1)]], device int* o [[buffer(2)]],
                      threadgroup atomic_int* t [[threadgroup(0)]],
                      uint i [[thread_position_in_grid]]) {
    o[i] = atomic_exchange_explicit(t, in[i], memory_order_relaxed);
}

// ===== AGGREGATE validation: many threads -> one location =====
// counter starts 0, each thread adds 1 -> final counter == grid size.
kernel void agg_add1(device atomic_int* c [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(c, 1, memory_order_relaxed);
}
