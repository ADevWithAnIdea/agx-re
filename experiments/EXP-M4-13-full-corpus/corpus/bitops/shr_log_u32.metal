#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]>>(b[i]&31u); }
