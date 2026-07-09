#include <metal_stdlib>
using namespace metal;
// int_arith :: uchar_arith -- isolates: 8-bit unsigned add/sub/mul
kernel void m(device uchar* o[[buffer(0)]],
              device const uchar* a[[buffer(1)]],
              device const uchar* b[[buffer(2)]],
              device const uchar* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i]*b[i] + a[i] - b[i];
}
