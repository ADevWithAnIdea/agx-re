#include <metal_stdlib>
using namespace metal;
// int_arith :: madsat_s32 -- isolates: signed saturating multiply-add
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = madsat(a[i], b[i], c[i]);
}
