#include <metal_stdlib>
using namespace metal;
// 64-bit half4 vector device load/store — 16-bit-per-lane vector memory op.
kernel void k(device half4* out [[buffer(0)]],
              device const half4* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    half4 v = in[i];
    out[i] = v.wzyx + half4(0.5h);
}
