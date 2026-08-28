#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o [[buffer(0)]], device const uint* a [[buffer(1)]],
              device atomic_uint* c [[buffer(2)]], uint tid [[thread_position_in_grid]]) {
    uint v = a[tid]; uint r = 0;
    for (uint i = 0; i < 8; ++i) {
        if ((v >> i) & 1u) { r += atomic_fetch_add_explicit(c, i, memory_order_relaxed); }
        else if (v > 100u) { r ^= atomic_fetch_or_explicit(c, 1u << i, memory_order_relaxed); }
        else { r += simd_sum(v + i); }
    }
    o[tid] = r;
}
