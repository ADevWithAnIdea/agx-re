#include <metal_stdlib>
using namespace metal;
kernel void probe(device atomic_uint *flag [[buffer(0)]], device uint *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    out[gid]=0x5a000000u|gid;
    atomic_thread_fence(mem_flags::mem_device,memory_order_release,thread_scope_device);
    atomic_fetch_add_explicit(flag,1u,memory_order_relaxed);
}
