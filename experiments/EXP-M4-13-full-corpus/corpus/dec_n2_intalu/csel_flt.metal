#include <metal_stdlib>
using namespace metal;
kernel void m(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
 device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
 device const float* d[[buffer(4)]], uint i[[thread_position_in_grid]]){ o[i]=(a[i]<b[i])?c[i]:d[i]; }
