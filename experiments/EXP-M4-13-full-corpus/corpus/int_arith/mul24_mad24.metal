#include <metal_stdlib>
using namespace metal;
// int_arith :: mul24_mad24 -- isolates: 24-bit multiply / multiply-add
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = mul24(a[i], b[i]) + mad24(a[i], b[i], c[i]);
}
