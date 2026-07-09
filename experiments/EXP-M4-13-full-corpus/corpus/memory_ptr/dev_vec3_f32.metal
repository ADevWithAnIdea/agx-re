#include <metal_stdlib>
using namespace metal;
// 96-bit float3 device load/store — 3-component mask, alignment quirks.
kernel void k(device float3* out [[buffer(0)]],
              device const float3* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    float3 v = in[i];
    out[i] = v.zyx * 2.0f;
}
