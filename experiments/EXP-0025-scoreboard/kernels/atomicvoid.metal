#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint *ctr [[buffer(0)]],
              device uint *out          [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(ctr, 1u, memory_order_relaxed);
    out[gid] = gid;
}
