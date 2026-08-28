#include <metal_stdlib>
using namespace metal;
kernel void k(device half4* out [[buffer(0)]], device const half4* a [[buffer(1)]], device const half4* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]+b[g]; }
