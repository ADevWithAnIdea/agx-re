// OWN-SHADER. Isolate half (fp16) fused multiply-add / mad and sign modifiers.
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              device const half* b[[buffer(2)]], device const half* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    half x=a[i], y=b[i], z=c[i];
    half r0 = fma(x, y, z);        // fma16
    half r1 = fma(-x, y, z);       // negated multiplicand -> src neg modifier
    half r2 = fma(x, -y, -z);      // multiple neg modifiers
    half r3 = fma(fabs(x), y, z);  // abs modifier on 16-bit src
    half r4 = x*y + z;             // mul-add (mad) fold
    o[i] = r0 + r1 + r2 + r3 + r4;
}
