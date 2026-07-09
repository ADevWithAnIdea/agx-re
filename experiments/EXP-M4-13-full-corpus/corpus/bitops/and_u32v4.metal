#include <metal_stdlib>
using namespace metal;
kernel void k(device uint4* o[[buffer(0)]], device const uint4* a[[buffer(1)]], device const uint4* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]&b[i]; }
