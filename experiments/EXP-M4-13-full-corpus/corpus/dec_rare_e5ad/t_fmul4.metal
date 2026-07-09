#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   device const float4* a[[buffer(1)]],
                   device const float4* b[[buffer(2)]],
                   uint i[[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
