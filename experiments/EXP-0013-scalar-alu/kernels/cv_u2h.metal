#include <metal_stdlib>
using namespace metal;

kernel void k(device const uint *a [[buffer(0)]],
              device half *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = half(a[gid]);
}
