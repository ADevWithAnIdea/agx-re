// OWN-SHADER. Isolate half division / reciprocal (recip16 + mul lowering).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              device const half* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half x=a[i], y=b[i];
    half r0 = x / y;                 // half divide
    half r1 = 1.0h / y;              // reciprocal (recip16)
    half r2 = precise::divide(x, y); // precise divide variant
    half r3 = x / (y + 1.0h);        // divide w/ add
    o[i] = r0 + r1 + r2 + r3;
}
