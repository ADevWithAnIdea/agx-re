#include <metal_stdlib>
using namespace metal;
kernel void p_hmin(device half* o[[buffer(0)]], device const half* a[[buffer(1)]], device const half* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=min(a[i],b[i]); }
