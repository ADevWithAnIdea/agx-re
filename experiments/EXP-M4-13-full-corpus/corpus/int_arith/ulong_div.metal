#include <metal_stdlib>
using namespace metal;
// int_arith :: ulong_div -- isolates: 64-bit unsigned division
kernel void m(device ulong* o[[buffer(0)]],
              device const ulong* a[[buffer(1)]],
              device const ulong* b[[buffer(2)]],
              device const ulong* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i] / (b[i] | 1);
}
