#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o, device const half2* a, device const half2* b, uint i[[thread_position_in_grid]]){ o[i]=a[i]*b[i]; }
