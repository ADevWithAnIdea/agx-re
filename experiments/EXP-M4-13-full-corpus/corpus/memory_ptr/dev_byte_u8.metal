#include <metal_stdlib>
using namespace metal;
// 8-bit unsigned byte device load (zero-extend) + store.
kernel void k(device uchar* out [[buffer(0)]],
              device const uchar* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uchar v = in[i];
    out[i] = uchar(v + 3);
}
