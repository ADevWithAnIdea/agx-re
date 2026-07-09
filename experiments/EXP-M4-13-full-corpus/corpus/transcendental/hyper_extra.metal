#include <metal_stdlib>
using namespace metal;
// isolate/probe: rarer transcendentals (inverse hyperbolic + tanpi)
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    float x = a[i];
    o[i*4+0] = asinh(x);
    o[i*4+1] = acosh(x);
    o[i*4+2] = atanh(x);
    o[i*4+3] = tanpi(x);
}
