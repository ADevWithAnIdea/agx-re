#include <metal_stdlib>
using namespace metal;
// int_arith :: hadd_rhadd_s32 -- isolates: signed averaging (hadd/rhadd)
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = hadd(a[i], b[i]) + rhadd(a[i], b[i]);
}
