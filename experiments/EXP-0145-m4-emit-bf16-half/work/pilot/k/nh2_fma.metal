#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* out [[buffer(0)]], device const half2* a [[buffer(1)]], device const half2* b [[buffer(2)]], device const half2* c [[buffer(3)]], uint g [[thread_position_in_grid]]){ out[g]=fma(a[g],b[g],c[g]); }
