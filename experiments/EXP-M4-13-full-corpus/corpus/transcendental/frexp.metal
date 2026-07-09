#include <metal_stdlib>
using namespace metal;
// isolate: frexp(x,&exp) — split mantissa/exponent
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              device int* oe[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    int e; float m = frexp(a[i], e); o[i] = m; oe[i] = e;
}
