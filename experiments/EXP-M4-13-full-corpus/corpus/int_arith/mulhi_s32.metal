#include <metal_stdlib>
using namespace metal;
// int_arith :: mulhi_s32 -- isolates: signed 32x32->high32 multiply
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = mulhi(a[i], b[i]);
}
