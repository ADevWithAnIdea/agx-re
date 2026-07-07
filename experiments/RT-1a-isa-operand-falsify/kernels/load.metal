#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(2)]],
              const device uint* a [[buffer(0)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid];
}
