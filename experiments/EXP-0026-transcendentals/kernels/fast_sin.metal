#include <metal_stdlib>
using namespace metal;

kernel void k(device const float* a [[buffer(0)]],
               device float* out [[buffer(1)]],
               uint gid [[thread_position_in_grid]]) {
    out[gid] = fast::sin(a[gid]);
}
