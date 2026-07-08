#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=fmin(a[i],b[i])+fmax(a[i],b[i]); }
