#include <metal_stdlib>
using namespace metal;
// 128-bit uint4 wide device load/store — full 4-component mask.
kernel void k(device uint4* out [[buffer(0)]],
              device const uint4* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uint4 v = in[i];
    out[i] = v.wzyx + uint4(1u,2u,3u,4u);
}
