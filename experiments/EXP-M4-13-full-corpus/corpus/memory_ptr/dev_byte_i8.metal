#include <metal_stdlib>
using namespace metal;
// 8-bit signed byte device load (sign-extend) + store, widened to int.
kernel void k(device char* out [[buffer(0)]],
              device const char* in [[buffer(1)]],
              device int* wide [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    char v = in[i];
    int e = int(v);            // sign extension of a signed byte
    wide[i] = e * 2;
    out[i] = char(v - 1);
}
