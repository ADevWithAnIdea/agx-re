#include <metal_stdlib>
using namespace metal;
// int_arith :: long_div -- isolates: 64-bit signed division
kernel void m(device long* o[[buffer(0)]],
              device const long* a[[buffer(1)]],
              device const long* b[[buffer(2)]],
              device const long* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i] / (b[i] | 1);
}
