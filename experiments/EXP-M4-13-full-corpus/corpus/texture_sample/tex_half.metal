// texture_sample corpus: half-precision texture sample(level)/gather/read (half return path).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device half4* o[[buffer(0)]],
                   texture2d<half> t[[texture(0)]],
                   sampler s[[sampler(0)]],
                   device const float2* c[[buffer(1)]],
                   uint2 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    half4 a   = t.sample(s, c[i], level(0.0));
    half4 b   = t.sample(s, c[i], level(2.0));
    half4 gth = t.gather(s, c[i], int2(1, 1), component::y);
    half4 r   = t.read(g);
    o[i] = a + b + gth + r;
}
