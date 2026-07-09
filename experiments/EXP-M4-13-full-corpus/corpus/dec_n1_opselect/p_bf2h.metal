#include <metal_stdlib>
using namespace metal;
kernel void p_bf2h(device half* o[[buffer(0)]], device const bfloat* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=half(a[i]); }
