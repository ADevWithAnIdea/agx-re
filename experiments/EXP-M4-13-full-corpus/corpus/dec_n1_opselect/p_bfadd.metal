#include <metal_stdlib>
using namespace metal;
kernel void p_bfadd(device bfloat* o[[buffer(0)]], device const bfloat* a[[buffer(1)]], device const bfloat* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
