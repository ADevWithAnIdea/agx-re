// EXP-0036 census corpus — TEXTURE compute kernels (OWN-SHADER).
// Sampling in compute uses explicit LOD (no derivatives). Covers sample/gather/
// compare/read/write/array/cube/3d/msaa/atomic/query.
#include <metal_stdlib>
using namespace metal;

kernel void k_tex_sample(device float4* o[[buffer(0)]], texture2d<float> t[[texture(0)]],
                        sampler s[[sampler(0)]], device const float2* c[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    o[i] = t.sample(s, c[i], level(0.0));
}
kernel void k_tex_lod(device float4* o[[buffer(0)]], texture2d<float> t[[texture(0)]],
                        sampler s[[sampler(0)]], device const float2* c[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    o[i] = t.sample(s, c[i], level(2.0)) + t.sample(s, c[i], bias(1.0))
         + t.sample(s, c[i], gradient2d(float2(0.1),float2(0.1)));
}
kernel void k_tex_gather(device float4* o[[buffer(0)]], texture2d<float> t[[texture(0)]],
                        sampler s[[sampler(0)]], device const float2* c[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    o[i] = t.gather(s, c[i], int2(0), component::x)
         + t.gather(s, c[i], int2(1,0), component::y)
         + t.gather(s, c[i], int2(0), component::z);
}
kernel void k_tex_compare(device float* o[[buffer(0)]], depth2d<float> t[[texture(0)]],
                        sampler s[[sampler(0)]], device const float2* c[[buffer(1)]],
                        device const float* r[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = t.sample_compare(s, c[i], r[i], level(0.0))
         + t.gather_compare(s, c[i], r[i]).x;
}
kernel void k_tex_rw(device float4* o[[buffer(0)]], texture2d<float,access::read> tr[[texture(0)]],
                        texture2d<float,access::write> tw[[texture(1)]],
                        uint2 g[[thread_position_in_grid]]) {
    float4 v = tr.read(g);
    tw.write(v*2.0, g);
    o[g.x] = v;
}
kernel void k_tex_array_cube(device float4* o[[buffer(0)]], texture2d_array<float> ta[[texture(0)]],
                        texturecube<float> tc[[texture(1)]], texture3d<float> t3[[texture(2)]],
                        sampler s[[sampler(0)]], device const float4* c[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    o[i] = ta.sample(s, c[i].xy, uint(c[i].z), level(0.0))
         + tc.sample(s, c[i].xyz, level(0.0))
         + t3.sample(s, c[i].xyz, level(0.0));
}
kernel void k_tex_atomic(device uint* o[[buffer(0)]], texture2d<uint,access::read_write> t[[texture(0)]],
                        texture_buffer<uint,access::read_write> tb[[texture(1)]],
                        uint2 g[[thread_position_in_grid]]) {
    t.atomic_fetch_add(g, 1u);
    tb.atomic_fetch_add(g.x, 1u);
    t.atomic_fetch_max(g, g.x);
    o[g.x] = t.read(g).x;
}
kernel void k_tex_query(device uint* o[[buffer(0)]], texture2d<float> t[[texture(0)]],
                        texture2d_array<float> ta[[texture(1)]], uint i[[thread_position_in_grid]]) {
    o[i] = t.get_width() + t.get_height() + t.get_num_mip_levels()
         + ta.get_array_size();
}
kernel void k_tex_msaa(device float4* o[[buffer(0)]], texture2d_ms<float> t[[texture(0)]],
                        uint2 g[[thread_position_in_grid]]) {
    o[g.x] = t.read(g, 0) + t.read(g, 1);
}
