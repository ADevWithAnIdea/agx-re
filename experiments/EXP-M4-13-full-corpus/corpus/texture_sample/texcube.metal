// texture_sample corpus: cube + cube-array sample(level) + gradientcube (cube addressing).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texturecube<float> tc[[texture(0)]],
                   texturecube_array<float> tca[[texture(1)]],
                   sampler s[[sampler(0)]],
                   device const float4* c[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    float3 d = c[i].xyz;
    float4 a = tc.sample(s, d, level(0.0));
    float4 b = tc.sample(s, d, gradientcube(float3(0.1), float3(0.2)));
    float4 e = tca.sample(s, d, uint(c[i].w), level(1.0));
    o[i] = a + b + e;
}
