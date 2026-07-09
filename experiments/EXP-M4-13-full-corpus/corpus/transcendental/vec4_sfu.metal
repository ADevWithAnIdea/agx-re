#include <metal_stdlib>
using namespace metal;
// isolate: SFU over float4 vector width (per-lane vectorization)
kernel void k(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    float4 x = a[i];
    o[i] = sin(x) + cos(x) + exp2(x) + log2(x) + rsqrt(x) + sqrt(x);
}
