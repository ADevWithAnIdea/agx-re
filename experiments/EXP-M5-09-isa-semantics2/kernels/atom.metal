// EXP-M5-09: Atomics provocations on M5 (int add/min/max/and/or/xor/xchg/cmpxchg + the
// M5-present float-add). Map the atomic-op selector + memory order.
// CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected. One op per kernel for byte-diff.
#include <metal_stdlib>
using namespace metal;

kernel void a_iadd(device atomic_int *p [[buffer(0)]], device const int *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_isub(device atomic_int *p [[buffer(0)]], device const int *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_sub_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_umin(device atomic_uint *p [[buffer(0)]], device const uint *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_min_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_umax(device atomic_uint *p [[buffer(0)]], device const uint *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_max_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_iand(device atomic_uint *p [[buffer(0)]], device const uint *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_and_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_ior(device atomic_uint *p [[buffer(0)]], device const uint *v [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    atomic_fetch_or_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_ixor(device atomic_uint *p [[buffer(0)]], device const uint *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_xor_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_xchg(device atomic_uint *p [[buffer(0)]], device const uint *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_exchange_explicit(p, v[i], memory_order_relaxed);
}
kernel void a_cmpxchg(device atomic_uint *p [[buffer(0)]], device uint *v [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) {
    uint expected = v[i];
    atomic_compare_exchange_weak_explicit(p, &expected, i, memory_order_relaxed, memory_order_relaxed);
}
kernel void a_fadd(device atomic<float> *p [[buffer(0)]], device const float *v [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(p, v[i], memory_order_relaxed);
}
// threadgroup-scope atomic add (different address space -> expose the space/scope field).
kernel void a_tgadd(device atomic_int *out [[buffer(0)]],
                    uint i [[thread_position_in_grid]], uint li [[thread_position_in_threadgroup]]) {
    threadgroup atomic_int acc;
    if (li == 0) atomic_store_explicit(&acc, 0, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(&acc, 1, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (li == 0) atomic_store_explicit(out, atomic_load_explicit(&acc, memory_order_relaxed), memory_order_relaxed);
}
