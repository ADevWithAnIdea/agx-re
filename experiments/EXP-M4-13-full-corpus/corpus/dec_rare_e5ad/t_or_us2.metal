#include <metal_stdlib>
using namespace metal;
kernel void k(device ushort2* o[[buffer(0)]], device const ushort2* a[[buffer(1)]], device const ushort2* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]|b[i]; }
