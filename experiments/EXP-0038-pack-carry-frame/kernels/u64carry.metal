#include <metal_stdlib>
using namespace metal;

// ---- Task 2: u64 carry-generate (0x32) ----
// EXP-0033: the compiler emits an explicit carry chain for 64-bit ADD
// (low 0x9f add + a 0x32 carry-generate + high add + carry add), while
// 64-bit SUB is a single native op. Provoke the add carry-chain.

kernel void k_u64add(device const ulong* a [[buffer(0)]],
                     device const ulong* b [[buffer(1)]],
                     device ulong* out      [[buffer(2)]],
                     uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

kernel void k_u64sub(device const ulong* a [[buffer(0)]],
                     device const ulong* b [[buffer(1)]],
                     device ulong* out      [[buffer(2)]],
                     uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] - b[gid];
}

// add a constant (forces carry from the low word into the high word).
kernel void k_u64addk(device const ulong* a [[buffer(0)]],
                      device ulong* out      [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + 1UL;
}

// chained 3-operand 64-bit add: two carry-generates.
kernel void k_u64add3(device const ulong* a [[buffer(0)]],
                      device const ulong* b [[buffer(1)]],
                      device const ulong* c [[buffer(2)]],
                      device ulong* out      [[buffer(3)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid] + c[gid];
}

// signed 64-bit add (carry semantics identical to unsigned low word).
kernel void k_i64add(device const long* a [[buffer(0)]],
                     device const long* b [[buffer(1)]],
                     device long* out      [[buffer(2)]],
                     uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

// 32-bit control (no carry chain -- plain iadd2).
kernel void k_u32add(device const uint* a [[buffer(0)]],
                     device const uint* b [[buffer(1)]],
                     device uint* out      [[buffer(2)]],
                     uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}
