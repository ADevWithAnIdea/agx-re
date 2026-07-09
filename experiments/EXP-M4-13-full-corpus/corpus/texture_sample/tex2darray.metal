// texture_sample corpus: 2D-array sample(level) + read(array,lod) + gather(array).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture2d_array<float> ta[[texture(0)]],
                   sampler s[[sampler(0)]],
                   device const float4* c[[buffer(1)]],
                   uint2 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    float4 a = ta.sample(s, c[i].xy, uint(c[i].z), level(2.0));
    float4 r = ta.read(g, uint(c[i].w), 0);
    float4 gg = ta.gather(s, c[i].xy, uint(c[i].z), int2(1, 0), component::y);
    o[i] = a + r + gg;
}
