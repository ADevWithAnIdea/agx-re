#include <metal_stdlib>
using namespace metal;
kernel void p_hfma(device half* o[[buffer(0)]], device const half* a[[buffer(1)]], device const half* b[[buffer(2)]], device const half* c[[buffer(3)]], uint i[[thread_position_in_grid]]){ o[i]=fma(a[i],b[i],c[i]); }
