// OWN-SHADER. Isolate half classification + specials (isnan/isinf/copysign/ldexp/frexp/modf).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]],
              device const half* a[[buffer(1)]],
              device const half* b[[buffer(2)]],
              uint i[[thread_position_in_grid]]) {
    half x=a[i], y=b[i];
    bool  n0 = isnan(x);
    bool  n1 = isinf(x);
    bool  n2 = isfinite(x);
    bool  n3 = isnormal(x);
    half  r0 = copysign(x, y);       // sign transplant on fp16
    half  r1 = ldexp(x, 3);          // x * 2^3
    int   e;
    half  r2 = frexp(x, e);          // mantissa/exponent split
    half  ip;
    half  r3 = modf(x, ip);          // integer/fraction split
    half  r4 = fabs(x);
    half  r5 = nextafter(x, y);
    o[i] = half(n0) + half(n1) + half(n2) + half(n3)
         + r0 + r1 + r2 + half(e) + r3 + ip + r4 + r5;
}
