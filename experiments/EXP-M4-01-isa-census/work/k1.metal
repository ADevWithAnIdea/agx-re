#include <metal_stdlib>
using namespace metal;
kernel void k1(device float* a [[buffer(0)]],
               device const float* b [[buffer(1)]],
               device atomic_uint* ctr [[buffer(2)]],
               uint gid [[thread_position_in_grid]]) {
    float x = b[gid];
    float acc = 0.0f;
    for (uint i = 0; i < gid; ++i) {
        acc += x * float(i) + 1.0f;
        if (acc > 100.0f) { acc = acc * 0.5f; }
    }
    a[gid] = fma(acc, x, b[gid]);
    if (acc > 50.0f) atomic_fetch_add_explicit(ctr, 1u, memory_order_relaxed);
}
