#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], device const uint* b[[buffer(2)]], device const uint* m[[buffer(3)]], uint i[[thread_position_in_grid]]){ o[i]=(m[i]&a[i])|(~m[i]&b[i]); }
