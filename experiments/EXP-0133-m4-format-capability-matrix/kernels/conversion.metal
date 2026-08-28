// EXP-0133 conversion-rule kernels. Extends EXP-0079's store+typed-read pattern
// (symmetric snorm scale, reduced-float truncation, unorm half-up ties) to
// 16-bit normalized formats, sRGB storage, integer-format linear filtering,
// and one compressed-format (BC1) decode. Each store kernel writes one
// authored constant; each read kernel performs one authored in-bounds typed
// read of the same texel. All literal inputs are chosen and registered
// in PRE_REGISTRATION.md before capture.
#include <metal_stdlib>
using namespace metal;

// ---- 16-bit normalized round/scale probes ----
kernel void s_r16unorm_sep_a(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.5 / 65535.0, 0, 0, 1), uint2(0, 0)); }
kernel void s_r16unorm_sep_b(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(2.5 / 65535.0, 0, 0, 1), uint2(0, 0)); }
kernel void s_r16unorm_nontie(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(5.9 / 65535.0, 0, 0, 1), uint2(0, 0)); }
kernel void s_r16snorm_m100(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(-1.0, 0, 0, 1), uint2(0, 0)); }
kernel void s_r16snorm_p100(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(1.0, 0, 0, 1), uint2(0, 0)); }
kernel void s_rgba16unorm_sep(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(2.5 / 65535.0, 1.5 / 65535.0, 0.0, 1.0), uint2(0, 0)); }

// ---- sRGB storage probes (RGBA8Unorm_sRGB) ----
kernel void s_srgb8_low(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.0031308, 0.0031308, 0.0031308, 1.0), uint2(0, 0)); }
kernel void s_srgb8_mid(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.5, 0.5, 0.5, 1.0), uint2(0, 0)); }
kernel void s_srgb8_high(texture2d<float, access::write> t [[texture(0)]]) { t.write(float4(0.95, 0.95, 0.95, 1.0), uint2(0, 0)); }

// ---- generic typed reads (name suffix documents the store texel byte width tested with it, not channel count -- every read here returns a float4) ----
kernel void k_read_float2(texture2d<float, access::read> t [[texture(0)]], device float* out [[buffer(0)]]) {
    float4 v = t.read(uint2(0, 0)); out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
kernel void k_read_float4(texture2d<float, access::read> t [[texture(0)]], device float* out [[buffer(0)]]) {
    float4 v = t.read(uint2(0, 0)); out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
kernel void k_read_float8(texture2d<float, access::read> t [[texture(0)]], device float* out [[buffer(0)]]) {
    float4 v = t.read(uint2(0, 0)); out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}

// ---- integer-format linear-filtering adversarial probe ----
kernel void k_sample_uint4(texture2d<uint, access::sample> t [[texture(0)]], sampler s [[sampler(0)]], device uint* out [[buffer(0)]]) {
    uint4 v = t.sample(s, float2(0.5, 0.5));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}

// ---- BC1 decode-only probe (compressed textures cannot be access::write; sample only) ----
kernel void k_read_bc1(texture2d<float, access::sample> t [[texture(0)]], device float* out [[buffer(0)]]) {
    constexpr sampler s(coord::normalized, filter::nearest);
    float4 v = t.sample(s, float2(0.5, 0.5));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}

// ---- split depth/stencil aspect probe (Depth32Float_Stencil8) -- duplicates the
// render-pipeline and stencil-view kernels from capability.metal since conversion
// mode compiles this file alone, not capability.metal ----
struct VOut { float4 position [[position]]; };
vertex VOut vs_fullscreen_z(uint vid [[vertex_id]], constant float& z [[buffer(0)]]) {
    float2 pos[3] = { float2(-1, -1), float2(3, -1), float2(-1, 3) };
    VOut o; o.position = float4(pos[vid], z, 1.0); return o;
}
fragment void fs_depth_only(VOut in [[stage_in]]) {}
kernel void k_sample_depth(depth2d<float, access::sample> t [[texture(0)]], sampler s [[sampler(0)]], device float* out [[buffer(0)]]) {
    float v = t.sample(s, float2(0.5, 0.5));
    out[0] = v; out[1] = 0; out[2] = 0; out[3] = 0;
}
kernel void k_read_uint(texture2d<uint, access::read> t [[texture(0)]], device uint* out [[buffer(0)]]) {
    uint4 v = t.read(uint2(0, 0));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
