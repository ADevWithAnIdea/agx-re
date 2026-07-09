#include <metal_stdlib>
using namespace metal;
// 64-bit ulong device load/store — wide integer memory + 64-bit arithmetic.
kernel void k(device ulong* out [[buffer(0)]],
              device const ulong* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    ulong v = in[i];
    out[i] = v * 0x0000000100000001ul + 9ul;
}
