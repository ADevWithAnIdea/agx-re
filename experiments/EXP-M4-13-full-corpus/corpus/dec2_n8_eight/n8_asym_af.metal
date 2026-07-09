#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o, device const half2* a, device const half2* b, device const half2* c, uint i[[thread_position_in_grid]]){ o[i]=half2(a[i].x+b[i].x, fma(a[i].y,b[i].y,c[i].y)); }
