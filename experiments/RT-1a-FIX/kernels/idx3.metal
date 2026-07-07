#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              const device uint* a [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    uint i = gid * 3;
    out[gid] = a[i];
}
