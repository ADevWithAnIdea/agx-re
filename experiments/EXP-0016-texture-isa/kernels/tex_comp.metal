#include <metal_stdlib>
using namespace metal;

// EXP-0016 texture/sample instruction battery -- COMPUTE stage.
// Compute extracts cleanly with shdump (__compute). Compute can sample only
// with EXPLICIT lod/gradient (no implicit derivatives), and is the natural
// stage for texture.read / texture.write / queries and for array/3D/cube/MSAA
// index operands. Each kernel forces one op so byte-diffs localize fields.
// Always write to a device buffer so nothing is dead-code-eliminated.
// Clean-room: OUR OWN MSL (OWN-SHADER).

// ---------- sample (explicit LOD, compute) ----------
kernel void c_sample_lod(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                         device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample(s, uv, level(0.0));
}

kernel void c_sample_grad(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                          device float4 *o [[buffer(0)]], device float2 *g [[buffer(1)]],
                          uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample(s, uv, gradient2d(g[i], g[i+1]));
}

// two textures -> texture slot field; two samplers -> sampler slot field
kernel void c_two_tex(texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]],
                      sampler s [[sampler(0)]], device float4 *o [[buffer(0)]],
                      uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t0.sample(s, uv, level(0.0)) + t1.sample(s, uv, level(0.0));
}

kernel void c_two_samp(texture2d<float> t [[texture(0)]],
                       sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]],
                       device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample(s0, uv, level(0.0)) + t.sample(s1, uv, level(0.0));
}

// ---------- texture read (no sampler) ----------
kernel void c_read(texture2d<float> t [[texture(0)]], device float4 *o [[buffer(0)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint2(i & 3, i >> 2));
}

kernel void c_read_lod(texture2d<float> t [[texture(0)]], device float4 *o [[buffer(0)]],
                       uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint2(i & 3, i >> 2), 1);        // explicit mip level operand
}

// ---------- texture write ----------
kernel void c_write(texture2d<float, access::write> t [[texture(0)]],
                    device float4 *in [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    t.write(in[i], uint2(i & 3, i >> 2));
}

kernel void c_readwrite(texture2d<float, access::read_write> t [[texture(0)]],
                        uint i [[thread_position_in_grid]]) {
    uint2 c = uint2(i & 3, i >> 2);
    float4 v = t.read(c);
    t.write(v + 1.0, c);
}

// ---------- array / 3D / cube / MSAA index operands ----------
kernel void c_read_array(texture2d_array<float> t [[texture(0)]], device float4 *o [[buffer(0)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint2(i & 3, i >> 2), i & 1);            // array index operand
}

kernel void c_read_3d(texture3d<float> t [[texture(0)]], device float4 *o [[buffer(0)]],
                      uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint3(i & 3, (i >> 2) & 3, i & 1));      // 3D z operand
}

kernel void c_sample_cube(texturecube<float> t [[texture(0)]], sampler s [[sampler(0)]],
                          device float4 *o [[buffer(0)]], device float3 *d [[buffer(1)]],
                          uint i [[thread_position_in_grid]]) {
    o[i] = t.sample(s, d[i], level(0.0));                  // cube 3D direction
}

kernel void c_sample_array(texture2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]],
                           device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample(s, uv, i & 1, level(0.0));             // sample from array slice
}

kernel void c_read_ms(texture2d_ms<float> t [[texture(0)]], device float4 *o [[buffer(0)]],
                      uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint2(i & 3, i >> 2), i & 3);            // MSAA sample index operand
}

// ---------- queries ----------
kernel void c_width(texture2d<float> t [[texture(0)]], device uint *o [[buffer(0)]],
                    uint i [[thread_position_in_grid]]) { o[i] = t.get_width(); }

kernel void c_height(texture2d<float> t [[texture(0)]], device uint *o [[buffer(0)]],
                     uint i [[thread_position_in_grid]]) { o[i] = t.get_height(); }

kernel void c_nmips(texture2d<float> t [[texture(0)]], device uint *o [[buffer(0)]],
                    uint i [[thread_position_in_grid]]) { o[i] = t.get_num_mip_levels(); }

kernel void c_nsamples(texture2d_ms<float> t [[texture(0)]], device uint *o [[buffer(0)]],
                       uint i [[thread_position_in_grid]]) { o[i] = t.get_num_samples(); }

kernel void c_warray(texture2d_array<float> t [[texture(0)]], device uint *o [[buffer(0)]],
                     uint i [[thread_position_in_grid]]) { o[i] = t.get_array_size(); }

// ---------- depth compare (PCF) ----------
kernel void c_depth_cmp(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                        device float *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample_compare(s, uv, 0.5, level(0.0));
}
