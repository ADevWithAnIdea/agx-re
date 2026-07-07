#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device float* a [[buffer(1)]], device float* b [[buffer(2)]], uint i [[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
