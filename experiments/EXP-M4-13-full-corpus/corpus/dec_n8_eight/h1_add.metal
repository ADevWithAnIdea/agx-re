#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o, device const half* a, device const half* b, uint i[[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
