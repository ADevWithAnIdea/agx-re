#include <metal_stdlib>
using namespace metal;
// Capability probe: 64-bit atomic fetch-add?
kernel void p_add64(device atomic_ulong* c [[buffer(0)]], device uint* in [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(c, ulong(in[i]), memory_order_relaxed);
}
