// texture_sample corpus: 1D + 1D-array sampling/read (1D addressing path).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture1d<float> t1[[texture(0)]],
                   texture1d_array<float> t1a[[texture(1)]],
                   sampler s[[sampler(0)]],
                   device const float* c[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    float4 a = t1.sample(s, c[i]);
    float4 b = t1a.sample(s, c[i], uint(c[i]));
    float4 r = t1.read(uint(c[i]));
    float4 ra = t1a.read(uint(c[i]), uint(c[i]));
    o[i] = a + b + r + ra;
}
