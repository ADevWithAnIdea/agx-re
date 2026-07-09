#include <metal_stdlib>
using namespace metal;
kernel void k(device half4* o, device const half4* a, device const half4* b, uint i[[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
