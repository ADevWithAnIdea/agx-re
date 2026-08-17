#include <metal_stdlib>
using namespace metal;
kernel void probe(device atomic_uint *flag [[buffer(0)]], device uint *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    out[gid]=atomic_fetch_add_explicit(flag,1u,memory_order_relaxed);
}
