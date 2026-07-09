// texture_sample corpus: 3D sample(level)+gradient3d + read(lod) + write (3D coords).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture3d<float> t3[[texture(0)]],
                   texture3d<float,access::write> tw[[texture(1)]],
                   sampler s[[sampler(0)]],
                   device const float4* c[[buffer(1)]],
                   uint3 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    float3 p = c[i].xyz;
    float4 a = t3.sample(s, p, level(1.0));
    float4 b = t3.sample(s, p, gradient3d(float3(0.1), float3(0.2)));
    float4 r = t3.read(g, 1);
    tw.write(a + b + r, g);
    o[i] = a + b + r;
}
