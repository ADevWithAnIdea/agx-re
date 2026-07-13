#include <metal_stdlib>
using namespace metal;
kernel void k(device const uint4* a [[buffer(0)]],
              device uint4* out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid];
}
