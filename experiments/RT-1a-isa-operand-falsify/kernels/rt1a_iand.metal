#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              const device uint* a [[buffer(1)]],
              const device uint* b [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] & b[gid];
}
