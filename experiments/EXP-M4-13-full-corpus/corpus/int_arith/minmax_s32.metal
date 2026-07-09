#include <metal_stdlib>
using namespace metal;
// int_arith :: minmax_s32 -- isolates: signed min/max/clamp
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = min(a[i], b[i]) + max(a[i], b[i]) + clamp(c[i], a[i], b[i]);
}
