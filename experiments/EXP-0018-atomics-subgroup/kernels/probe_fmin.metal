#include <metal_stdlib>
using namespace metal;
// Capability probe: does MSL expose a FLOAT atomic min?
kernel void p_fmin(device atomic_float* c [[buffer(0)]], device float* in [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_min_explicit(c, in[i], memory_order_relaxed);
}
