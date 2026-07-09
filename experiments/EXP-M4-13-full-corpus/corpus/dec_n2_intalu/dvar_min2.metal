#include <metal_stdlib>
using namespace metal;
// two independent int mins stored to two outputs -> forces two live dst regs
kernel void m(device int* o0[[buffer(0)]], device int* o1[[buffer(1)]],
              device const int* a[[buffer(2)]], device const int* b[[buffer(3)]],
              device const int* c[[buffer(4)]], uint i[[thread_position_in_grid]]) {
    int m0 = min(a[i], b[i]);
    int m1 = min(b[i], c[i]);
    o0[i] = m0 + m1;   // keep both live
    o1[i] = m0 - m1;
}
