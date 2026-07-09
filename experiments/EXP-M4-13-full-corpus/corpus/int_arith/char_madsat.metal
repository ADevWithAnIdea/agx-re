#include <metal_stdlib>
using namespace metal;
// int_arith :: char_madsat -- isolates: PROBE: 8-bit saturating multiply-add
kernel void m(device char* o[[buffer(0)]],
              device const char* a[[buffer(1)]],
              device const char* b[[buffer(2)]],
              device const char* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = madsat(a[i], b[i], c[i]);
}
