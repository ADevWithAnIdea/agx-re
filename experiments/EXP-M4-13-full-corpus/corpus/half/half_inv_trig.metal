// OWN-SHADER. Isolate half inverse trig (asin/acos/atan/atan2 on fp16).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              device const half* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half x=a[i], y=b[i];
    half r0 = asin(x);
    half r1 = acos(x);
    half r2 = atan(x);
    half r3 = atan2(y, x);   // two-arg arctangent
    o[i] = r0 + r1 + r2 + r3;
}
