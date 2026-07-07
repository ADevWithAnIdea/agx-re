#include <metal_stdlib>
using namespace metal;

// EXP-0034 texture-variant battery -- COMPUTE stage. Extends EXP-0016.
// Each kernel provokes exactly ONE texture variant so byte-diffing localizes the
// field that encodes it. Always write to a device buffer so nothing is DCE'd.
// Clean-room: OUR OWN MSL (OWN-SHADER).

// ============ baseline (must match EXP-0016 for cross-diff) ============
kernel void b_sample_lod(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                         device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample(s, uv, level(0.0));
}
kernel void b_gather(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                     device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv);
}

// ============ 1. GATHER component enum (x/y/z/w) ============
kernel void g_x(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv, int2(0), component::x);
}
kernel void g_y(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv, int2(0), component::y);
}
kernel void g_z(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv, int2(0), component::z);
}
kernel void g_w(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv, int2(0), component::w);
}

// ============ 2. TEXEL-OFFSET gather (constant offset) ============
kernel void g_off10(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                    device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv, int2(1, 0));          // +1 in x
}
kernel void g_off01(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                    device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv, int2(0, 1));          // +1 in y
}
kernel void g_off33(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                    device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather(s, uv, int2(3, -2));         // distinct x,y offsets
}

// ============ 3. SAMPLE with constant texel offset ============
kernel void s_off(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                  device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample(s, uv, level(0.0), int2(1, 1));
}

// ============ 4. SAMPLE_COMPARE variants (depth PCF) ============
kernel void sc_lod(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                   device float *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample_compare(s, uv, 0.5, level(0.0));
}
kernel void sc_ref(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                   device float *o [[buffer(0)]], device float *ref [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample_compare(s, uv, ref[i], level(0.0));   // ref from a register (not const)
}
kernel void sc_off(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                   device float *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample_compare(s, uv, 0.5, level(0.0), int2(1, 0));
}

// ============ 5. GATHER_COMPARE (PCF gather) ============
kernel void gc(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
               device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather_compare(s, uv, 0.5);
}
kernel void gc_off(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                   device float4 *o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.gather_compare(s, uv, 0.5, int2(1, 0));
}

// ============ 6. LOD QUERY (calculate_clamped/unclamped_lod) ============
kernel void lod_c(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                  device float *o [[buffer(0)]], device float2 *uvb [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = t.calculate_clamped_lod(s, uvb[i]);
}
kernel void lod_u(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                  device float *o [[buffer(0)]], device float2 *uvb [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = t.calculate_unclamped_lod(s, uvb[i]);
}

// ============ 7. array / 3D / cube / MSAA SAMPLE coordinate operands ============
kernel void s_array(texture2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]],
                    device float4 *o [[buffer(0)]], device uint *sl [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    float2 uv = float2(float(i & 3), float(i >> 2)) / 4.0;
    o[i] = t.sample(s, uv, sl[i], level(0.0));            // array slice from a register
}
kernel void s_cube(texturecube<float> t [[texture(0)]], sampler s [[sampler(0)]],
                   device float4 *o [[buffer(0)]], device float3 *d [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = t.sample(s, d[i], level(0.0));                 // cube 3D direction
}
kernel void s_cube_array(texturecube_array<float> t [[texture(0)]], sampler s [[sampler(0)]],
                         device float4 *o [[buffer(0)]], device float3 *d [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) {
    o[i] = t.sample(s, d[i], i & 1, level(0.0));          // cube-array: dir + slice
}
kernel void s_3d(texture3d<float> t [[texture(0)]], sampler s [[sampler(0)]],
                 device float4 *o [[buffer(0)]], device float3 *d [[buffer(1)]],
                 uint i [[thread_position_in_grid]]) {
    o[i] = t.sample(s, d[i], level(0.0));                 // 3D uvw
}
kernel void r_ms_s(texture2d_ms<float> t [[texture(0)]], device float4 *o [[buffer(0)]],
                   device uint *sm [[buffer(1)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.read(uint2(i & 3, i >> 2), sm[i]);           // MSAA sample index from a register
}
