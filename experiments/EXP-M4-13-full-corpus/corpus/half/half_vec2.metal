// OWN-SHADER. Isolate packed 2-lane half2 ALU (16x2 packed arithmetic + fma).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o[[buffer(0)]], device const half2* a[[buffer(1)]],
              device const half2* b[[buffer(2)]], device const half2* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    half2 x=a[i], y=b[i], z=c[i];
    half2 r0 = x*y + z;      // packed mad
    half2 r1 = fma(x, y, z); // packed fma
    half2 r2 = x - y;
    half2 r3 = min(x, y);
    half2 r4 = x.yx * y.xy;  // swizzle exercises lane select
    o[i] = r0 + r1 + r2 + r3 + r4;
}
