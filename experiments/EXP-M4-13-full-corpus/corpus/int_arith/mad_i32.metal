#include <metal_stdlib>
using namespace metal;
// int_arith :: mad_i32 -- isolates: signed 32-bit multiply-add
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i]*b[i] + c[i];
}
