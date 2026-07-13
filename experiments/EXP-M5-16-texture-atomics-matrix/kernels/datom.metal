// EXP-M5-16: DIVERGENT-ADDRESS device atomics on M5. Each lane atomically updates a
// DIFFERENT element (buf[gid]) -> the per-lane divergent-atomic path (A18: 0x67 b+1
// 0x11/0x01, "gone" on M5). CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
using namespace metal;

kernel void da_add(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(&b[gid], x[gid], memory_order_relaxed);
}
kernel void da_min(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    atomic_fetch_min_explicit(&b[gid], x[gid], memory_order_relaxed);
}
kernel void da_max(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    atomic_fetch_max_explicit(&b[gid], x[gid], memory_order_relaxed);
}
kernel void da_and(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    atomic_fetch_and_explicit(&b[gid], x[gid], memory_order_relaxed);
}
kernel void da_or(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                  uint gid [[thread_position_in_grid]]) {
    atomic_fetch_or_explicit(&b[gid], x[gid], memory_order_relaxed);
}
kernel void da_xor(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    atomic_fetch_xor_explicit(&b[gid], x[gid], memory_order_relaxed);
}
kernel void da_xchg(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    atomic_exchange_explicit(&b[gid], x[gid], memory_order_relaxed);
}
kernel void da_cmpxchg(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    uint expected = 0;
    atomic_compare_exchange_weak_explicit(&b[gid], &expected, x[gid],
                                          memory_order_relaxed, memory_order_relaxed);
}
kernel void da_fadd(device atomic_float *b [[buffer(0)]], device float *x [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(&b[gid], x[gid], memory_order_relaxed);
}
// contrast: UNIFORM-address atomic (all lanes same addr) -> the m5_reduce pre-combine path.
kernel void ua_add(device atomic_uint *b [[buffer(0)]], device uint *x [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(&b[0], x[gid], memory_order_relaxed);
}
