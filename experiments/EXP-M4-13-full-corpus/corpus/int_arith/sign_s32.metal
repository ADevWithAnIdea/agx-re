#include <metal_stdlib>
using namespace metal;
// int_arith :: sign_s32 -- isolates: signum via compare+sub
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = (a[i] > 0) - (a[i] < 0);
}
