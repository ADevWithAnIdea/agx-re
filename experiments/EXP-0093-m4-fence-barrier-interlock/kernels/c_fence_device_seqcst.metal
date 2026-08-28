#include <metal_stdlib>
using namespace metal;
// Standalone device-scope seq_cst fence, no execution barrier -- reproduces
// EXP-O2D's mem_fence probe on this exact toolchain (own-compile check of
// `07 04 54 84 0a 00`).
kernel void k_main(device atomic_uint *counter [[buffer(0)]],
                    device float *payload [[buffer(1)]],
                    uint tid [[thread_position_in_grid]]) {
    payload[tid] = float(tid) * 2.0;
    atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device);
    atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
}
