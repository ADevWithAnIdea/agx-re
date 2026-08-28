#include <metal_stdlib>
using namespace metal;
kernel void k(device bfloat2* out [[buffer(0)]], device const bfloat2* a [[buffer(1)]], device const bfloat2* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]+b[g]; }
