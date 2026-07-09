#include <metal_stdlib>
using namespace metal;
kernel void p_bffma(device bfloat* o[[buffer(0)]], device const bfloat* a[[buffer(1)]], device const bfloat* b[[buffer(2)]], device const bfloat* c[[buffer(3)]], uint i[[thread_position_in_grid]]){ o[i]=bfloat(a[i]*b[i]+c[i]); }
