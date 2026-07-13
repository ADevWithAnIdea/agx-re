// EXP-M5-09: Texture sample/gather/read/LOD-query provocations on M5 (the real texture
// ops, distinct from the load family). CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
using namespace metal;

// plain sample at a coordinate (filtered).
kernel void tex_sample(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                       device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.sample(s, float2(0.5, 0.5));
}

// sample at an explicit LOD.
kernel void tex_lod(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                    device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.sample(s, float2(0.5, 0.5), level(2.0));
}

// gather (2x2 footprint, one channel).
kernel void tex_gather(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                       device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.gather(s, float2(0.5, 0.5));
}

// unfiltered read (image load by integer coord).
kernel void tex_read(texture2d<float> t [[texture(0)]],
                     device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint2(1, 1));
}

// LOD query (calculate_clamped_lod).
kernel void tex_lodq(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                     device float *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.calculate_clamped_lod(s, float2(0.5, 0.5));
}

// sample_compare (depth compare / shadow).
kernel void tex_scmp(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                     device float *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.sample_compare(s, float2(0.5, 0.5), 0.5);
}

// image write (store).
kernel void tex_write(texture2d<float, access::write> t [[texture(0)]],
                      uint i [[thread_position_in_grid]]) {
    t.write(float4(1,0,0,1), uint2(i, 0));
}
