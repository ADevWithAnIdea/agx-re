#include <metal_stdlib>
using namespace metal;
kernel void p_fmax(device atomic_float* c [[buffer(0)]], device float* in [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    atomic_fetch_max_explicit(c, in[i], memory_order_relaxed);
}
