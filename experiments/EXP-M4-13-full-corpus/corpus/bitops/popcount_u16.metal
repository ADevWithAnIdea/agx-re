#include <metal_stdlib>
using namespace metal;
kernel void k(device ushort* o[[buffer(0)]], device const ushort* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ o[i]=popcount(a[i]); }
