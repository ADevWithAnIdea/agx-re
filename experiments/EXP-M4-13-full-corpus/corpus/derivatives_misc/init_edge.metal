#include <metal_stdlib>
using namespace metal;
// Initializer / immediate edge cases: +/-INFINITY, NAN, FLT_MAX, min normal,
// a denormal, -0.0, hex float literal, and half extremes (65504, half-inf).
// Forces the compiler to emit the exact fp immediate encodings.
kernel void k(device float* o [[buffer(0)]],
              device half*  oh [[buffer(1)]],
              device const uint* idx [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    float fv[8] = {
        INFINITY, -INFINITY, NAN, 0x1.fffffep127f,
        0x1.0p-126f, 1.0e-45f, -0.0f, 0x1.921fb6p1f
    };
    half hv[4] = { half(INFINITY), 65504.0h, -0.0h, 0x1.ffcp-1h };
    uint j = idx[i];
    o[i]  = fv[j & 7u];
    oh[i] = hv[j & 3u];
}
