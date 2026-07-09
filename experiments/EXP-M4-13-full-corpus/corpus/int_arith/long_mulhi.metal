#include <metal_stdlib>
using namespace metal;
// int_arith :: long_mulhi -- isolates: PROBE: 64-bit high-multiply support
kernel void m(device long* o[[buffer(0)]],
              device const long* a[[buffer(1)]],
              device const long* b[[buffer(2)]],
              device const long* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = mulhi(a[i], b[i]);
}
