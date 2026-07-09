#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], device const uint* b[[buffer(2)]], device const uint* c[[buffer(3)]], uint i[[thread_position_in_grid]]){ uint n=c[i]&31u; o[i]=(a[i]<<n)|(b[i]>>(32u-n)); }
