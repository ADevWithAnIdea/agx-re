#include <metal_stdlib>
using namespace metal;
kernel void p_f2bf(device bfloat* o[[buffer(0)]], device const float* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=bfloat(a[i]); }
