#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o, device const half2* a, device const half2* b, device const half2* c, uint i[[thread_position_in_grid]]){ o[i]=fma(a[i],b[i],c[i]); }
