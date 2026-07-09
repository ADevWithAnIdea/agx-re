#include <metal_stdlib>
using namespace metal;
kernel void k(device half4* o, device const half4* a, device const half4* b, device const half4* c, uint i[[thread_position_in_grid]]){ o[i]=fma(a[i],b[i],c[i]); }
