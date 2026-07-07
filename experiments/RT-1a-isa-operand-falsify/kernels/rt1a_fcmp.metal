#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              const device float* a [[buffer(1)]],
              const device float* b [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = (a[gid] < b[gid]) ? 1u : 0u;
}
