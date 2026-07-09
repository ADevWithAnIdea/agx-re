#include <metal_stdlib>
using namespace metal;
// Single fma; result stored -> allocated to the store register (usually r0).
kernel void k_fma_one(device float* out [[buffer(0)]],
                      device const float* a [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = fma(a[gid+0], a[gid+1], a[gid+2]);
}
