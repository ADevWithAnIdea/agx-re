// texture_sample corpus: inline constexpr samplers — unnormalized coord::pixel vs normalized/repeat.
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture2d<float> t[[texture(0)]],
                   device const float2* c[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    constexpr sampler ps(coord::pixel, address::clamp_to_edge, filter::nearest, mip_filter::none);
    constexpr sampler ns(coord::normalized, address::repeat, filter::linear, mip_filter::linear);
    float4 a = t.sample(ps, c[i] * 256.0, level(0.0));
    float4 b = t.sample(ns, c[i], level(1.0));
    o[i] = a + b;
}
