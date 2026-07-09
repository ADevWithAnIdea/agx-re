#include <metal_stdlib>
using namespace metal;
// int_arith :: short_arith -- isolates: 16-bit signed add/sub/mul
kernel void m(device short* o[[buffer(0)]],
              device const short* a[[buffer(1)]],
              device const short* b[[buffer(2)]],
              device const short* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i]*b[i] + a[i] - b[i];
}
