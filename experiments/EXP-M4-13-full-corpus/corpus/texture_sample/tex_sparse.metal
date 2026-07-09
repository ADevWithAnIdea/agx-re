// texture_sample corpus (EXTRAPOLATION / rare): sparse residency sampling+read.
// sparse_sample / sparse_read return a sparse_color carrying a residency predicate.
// If this fails to compile the feature is unavailable/emulated — a first-class NEGATIVE.
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   device uint* res[[buffer(2)]],
                   texture2d<float> t[[texture(0)]],
                   sampler s[[sampler(0)]],
                   device const float2* c[[buffer(1)]],
                   uint2 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    sparse_color<vec<float,4>> sc = t.sparse_sample(s, c[i], level(0.0));
    float4 v = sc.value();
    bool r = sc.resident();
    sparse_color<vec<float,4>> sr = t.sparse_read(g);
    o[i] = v + sr.value();
    res[i] = (r ? 1u : 0u) + (sr.resident() ? 2u : 0u);
}
