#include <metal_stdlib>
using namespace metal;

kernel void clzu(device const uint *a [[buffer(0)]],
                  device uint *out [[buffer(1)]],
                  uint gid [[thread_position_in_grid]]) {
    out[gid] = clz(a[gid]);
}

kernel void popc(device const uint *a [[buffer(0)]],
                  device uint *out [[buffer(1)]],
                  uint gid [[thread_position_in_grid]]) {
    out[gid] = popcount(a[gid]);
}
