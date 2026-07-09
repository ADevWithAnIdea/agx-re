// texture_sample corpus: multisample read(sample-index) 2d_ms + 2d_ms_array + num_samples.
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture2d_ms<float> tm[[texture(0)]],
                   texture2d_ms_array<float> tma[[texture(1)]],
                   uint2 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    float4 a = tm.read(g, 0) + tm.read(g, 3);
    float4 b = tma.read(g, uint(2), 1);
    uint ns = tm.get_num_samples() + tma.get_num_samples();
    o[i] = a + b + float4(ns);
}
