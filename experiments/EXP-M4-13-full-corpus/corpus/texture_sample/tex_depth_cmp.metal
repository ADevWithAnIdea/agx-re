// texture_sample corpus: depth compare across depth2d / depth2d_array / depthcube +
// gather_compare + a plain depth read. Explicit level() so it is valid in compute.
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float* o[[buffer(0)]],
                   depth2d<float> d2[[texture(0)]],
                   depth2d_array<float> d2a[[texture(1)]],
                   depthcube<float> dc[[texture(2)]],
                   sampler s[[sampler(0)]],
                   device const float4* c[[buffer(1)]],
                   device const float* r[[buffer(2)]],
                   uint i[[thread_position_in_grid]]) {
    float a  = d2.sample_compare(s, c[i].xy, r[i], level(0.0));
    float g  = d2.gather_compare(s, c[i].xy, r[i]).x;
    float b  = d2a.sample_compare(s, c[i].xy, uint(c[i].z), r[i], level(0.0));
    float e  = dc.sample_compare(s, c[i].xyz, r[i], level(0.0));
    float pl = d2.sample(s, c[i].xy, level(0.0));
    o[i] = a + g + b + e + pl;
}
