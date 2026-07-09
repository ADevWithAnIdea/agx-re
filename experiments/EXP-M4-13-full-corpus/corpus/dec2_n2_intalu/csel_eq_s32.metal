#include <metal_stdlib>
using namespace metal;
kernel void m(device int* o[[buffer(0)]],device const int* a[[buffer(1)]],device const int* b[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=(a[i]==b[i])?1:0;}
