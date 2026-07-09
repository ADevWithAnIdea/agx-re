#include <metal_stdlib>
using namespace metal;
// Fixed compile-time element offsets from a single base — surfaces
// immediate-offset addressing (small vs large offsets) in load/store.
kernel void k(device float* out [[buffer(0)]],
              device const float* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    device const float* p = in + i * 64u;
    float s = p[0] + p[1] + p[7] + p[31] + p[63] + p[40];
    out[i] = s;
}
