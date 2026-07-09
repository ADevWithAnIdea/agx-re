// OWN-SHADER. Isolate half sqrt/rsqrt/pow/powr (root + power on fp16).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              device const half* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half x=a[i], y=b[i];
    half r0 = sqrt(x);        // native fp16 sqrt
    half r1 = rsqrt(x);       // native fp16 rsqrt
    half r2 = pow(x, y);      // pow lowering
    half r3 = powr(x, y);     // powr (x>=0) variant
    half r4 = precise::sqrt(x);
    o[i] = r0 + r1 + r2 + r3 + r4;
}
