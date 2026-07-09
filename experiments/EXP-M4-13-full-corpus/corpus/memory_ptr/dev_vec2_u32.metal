#include <metal_stdlib>
using namespace metal;
// 64-bit combined (uint2) device load/store — 2-component mask.
kernel void k(device uint2* out [[buffer(0)]],
              device const uint2* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uint2 v = in[i];
    out[i] = v.yx + 1u;
}
