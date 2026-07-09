#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture2d<float> t[[texture(0)]],
                   sampler s[[sampler(0)]],
                   device const float2* c[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    o[i] = t.sample(s, c[i]);
}
