#include <metal_stdlib>
using namespace metal;
// isolate: ldexp(x, int) — scale by 2^n
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              device const int* e[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = ldexp(a[i], e[i]);
}
