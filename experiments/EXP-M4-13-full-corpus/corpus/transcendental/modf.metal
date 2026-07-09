#include <metal_stdlib>
using namespace metal;
// isolate: modf(x,&ip) — split integer/fractional parts
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              device float* oi[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    float ip; float f = modf(a[i], ip); o[i] = f; oi[i] = ip;
}
