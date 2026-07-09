// OWN-SHADER. Isolate half min/max/clamp/saturate/sign/step/smoothstep on fp16.
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              device const half* b[[buffer(2)]], device const half* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    half x=a[i], y=b[i], z=c[i];
    half r0 = min(x, y);
    half r1 = max(x, y);
    half r2 = fmin(x, y);          // NaN-propagation variant
    half r3 = fmax(x, y);
    half r4 = clamp(x, y, z);
    half r5 = saturate(x);         // clamp to [0,1] (may be modifier)
    half r6 = sign(x);
    half r7 = step(y, x);
    half r8 = smoothstep(y, z, x);
    o[i] = r0 + r1 + r2 + r3 + r4 + r5 + r6 + r7 + r8;
}
