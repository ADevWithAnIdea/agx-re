#include <metal_stdlib>
using namespace metal;
kernel void k(device uint2* o[[buffer(0)]], device const uint2* a[[buffer(1)]], device const uint2* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]<<(b[i]&31u); }
