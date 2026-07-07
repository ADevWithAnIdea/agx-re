#include <metal_stdlib>
using namespace metal;

// ============ Sub-experiment 2: 64-bit atomic min/max (width field) ============
// atomic<ulong>/atomic<long> template form (atomic_ulong typedef is not defined).
// Decode the width field distinguishing 32- vs 64-bit atomics on the 0x67 RMW op.

// ---- 32-bit references ----
kernel void a32_umin(device atomic<uint>* a [[buffer(0)]],
                     device const uint* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_fetch_min_explicit(a, v[i], memory_order_relaxed);
}
kernel void a32_umax(device atomic<uint>* a [[buffer(0)]],
                     device const uint* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_fetch_max_explicit(a, v[i], memory_order_relaxed);
}
kernel void a32_add(device atomic<uint>* a [[buffer(0)]],
                    device const uint* v [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(a, v[i], memory_order_relaxed);
}
kernel void a32_xchg(device atomic<uint>* a [[buffer(0)]],
                     device const uint* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_exchange_explicit(a, v[i], memory_order_relaxed);
}

// ---- 64-bit (ulong/long) ----
kernel void a64_umin(device atomic<ulong>* a [[buffer(0)]],
                     device const ulong* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_fetch_min_explicit(a, v[i], memory_order_relaxed);
}
kernel void a64_umax(device atomic<ulong>* a [[buffer(0)]],
                     device const ulong* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_fetch_max_explicit(a, v[i], memory_order_relaxed);
}
kernel void a64_smin(device atomic<long>* a [[buffer(0)]],
                     device const long* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_fetch_min_explicit(a, v[i], memory_order_relaxed);
}
kernel void a64_smax(device atomic<long>* a [[buffer(0)]],
                     device const long* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_fetch_max_explicit(a, v[i], memory_order_relaxed);
}
kernel void a64_add(device atomic<ulong>* a [[buffer(0)]],
                    device const ulong* v [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(a, v[i], memory_order_relaxed);
}
kernel void a64_xchg(device atomic<ulong>* a [[buffer(0)]],
                     device const ulong* v [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    atomic_exchange_explicit(a, v[i], memory_order_relaxed);
}
kernel void a64_and(device atomic<ulong>* a [[buffer(0)]],
                    device const ulong* v [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    atomic_fetch_and_explicit(a, v[i], memory_order_relaxed);
}
