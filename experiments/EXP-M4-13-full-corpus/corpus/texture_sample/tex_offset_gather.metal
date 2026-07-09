// texture_sample corpus: sample(level,offset) + gather all 4 components with offsets.
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture2d<float> t[[texture(0)]],
                   sampler s[[sampler(0)]],
                   device const float2* c[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    float4 a  = t.sample(s, c[i], level(0.0), int2(2, -1));
    float4 gx = t.gather(s, c[i], int2(0, 0),  component::x);
    float4 gy = t.gather(s, c[i], int2(1, 0),  component::y);
    float4 gz = t.gather(s, c[i], int2(0, 1),  component::z);
    float4 gw = t.gather(s, c[i], int2(-1,-1), component::w);
    o[i] = a + gx + gy + gz + gw;
}
