// OWN-SHADER. Isolate half trigonometric transcendentals (sin/cos/tan on fp16).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    half x=a[i];
    half r0 = sin(x);
    half r1 = cos(x);
    half r2 = tan(x);
    half r3 = sinpi(x);   // sin(pi*x) variant
    half r4 = cospi(x);
    o[i] = r0 + r1 + r2 + r3 + r4;
}
