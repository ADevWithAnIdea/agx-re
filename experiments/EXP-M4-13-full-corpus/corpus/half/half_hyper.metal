// OWN-SHADER. Isolate half hyperbolic + inverse hyperbolic on fp16.
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    half x=a[i];
    half r0 = sinh(x);
    half r1 = cosh(x);
    half r2 = tanh(x);
    half r3 = asinh(x);
    half r4 = acosh(x + 1.0h);
    half r5 = atanh(x * 0.5h);
    o[i] = r0 + r1 + r2 + r3 + r4 + r5;
}
