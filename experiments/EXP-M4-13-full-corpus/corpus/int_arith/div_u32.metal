#include <metal_stdlib>
using namespace metal;
// int_arith :: div_u32 -- isolates: unsigned 32-bit division
kernel void m(device uint* o[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              device const uint* b[[buffer(2)]],
              device const uint* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i] / (b[i] | 1u);
}
