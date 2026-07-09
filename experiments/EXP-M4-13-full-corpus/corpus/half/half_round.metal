// OWN-SHADER. Isolate half rounding/round-mode ops (floor/ceil/trunc/rint/round/fract).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    half x=a[i];
    half r0 = floor(x);   // round toward -inf
    half r1 = ceil(x);    // round toward +inf
    half r2 = trunc(x);   // round toward zero
    half r3 = rint(x);    // round to nearest even
    half r4 = round(x);   // round half away from zero
    half r5 = fract(x);   // fractional part
    o[i] = r0 + r1 + r2 + r3 + r4 + r5;
}
