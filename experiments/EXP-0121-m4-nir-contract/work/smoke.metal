#include <metal_stdlib>
using namespace metal;

kernel void k_div_precisens(device float* a [[buffer(0)]], device float* b [[buffer(1)]],
                              device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = precise::divide(a[gid], b[gid]);
}

struct MB { uint payload[4]; atomic_uint ready; atomic_uint ack; };

kernel void k_plain_access(volatile device MB* boxes [[buffer(0)]],
                            device uint* out [[buffer(1)]],
                            uint gid [[thread_position_in_grid]]) {
    volatile device MB* m = &boxes[0];
    // plain store through reinterpret of atomic_uint*
    *(volatile device uint*)(&m->ready) = gid;
    uint v = *(volatile const device uint*)(&m->ready);
    atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device);
    out[gid] = v;
}

kernel void k_switch_cond(device float* a, device float* b, device uint* cond, device float* out,
                           uint gid [[thread_position_in_grid]]) {
    float A = a[gid], B = b[gid];
    bool p;
    switch (cond[gid]) {
        case 0u: p = A == B; break;
        case 1u: p = A != B; break;
        case 2u: p = A <  B; break;
        default: p = false; break;
    }
    out[gid] = select(B, A, p);
}
