#include <metal_stdlib>
using namespace metal;
// int_arith :: ushort_arith -- isolates: 16-bit unsigned add/sub/mul
kernel void m(device ushort* o[[buffer(0)]],
              device const ushort* a[[buffer(1)]],
              device const ushort* b[[buffer(2)]],
              device const ushort* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i]*b[i] + a[i] - b[i];
}
