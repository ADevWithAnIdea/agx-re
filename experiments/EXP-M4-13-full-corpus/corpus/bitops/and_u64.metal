#include <metal_stdlib>
using namespace metal;
kernel void k(device ulong* o[[buffer(0)]], device const ulong* a[[buffer(1)]], device const ulong* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]&b[i]; }
