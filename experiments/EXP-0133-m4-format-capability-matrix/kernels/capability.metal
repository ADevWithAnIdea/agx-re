// EXP-0133 capability-sweep kernels. Authored MSL, format-agnostic: every
// MTLPixelFormat under test is bound at runtime by the Obj-C harness to
// whichever of these fixed kernels matches its numeric "kind" (float / uint
// / int / depth). No kernel here depends on which specific pixel format is
// bound -- the format identity lives entirely in the MTLTexture object
// constructed by harness/probe.m, so this one small compiled library serves
// all 138 formats in the target matrix.
#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------- sample (used for both "sampled" [nearest] and "filtered" [linear] axes -- the sampler's filter mode is set by the Obj-C harness, not this kernel)
kernel void k_sample_float(texture2d<float, access::sample> t [[texture(0)]], sampler s [[sampler(0)]], device float* out [[buffer(0)]]) {
    float4 v = t.sample(s, float2(0.5, 0.5));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
kernel void k_sample_uint(texture2d<uint, access::sample> t [[texture(0)]], sampler s [[sampler(0)]], device uint* out [[buffer(0)]]) {
    uint4 v = t.sample(s, float2(0.5, 0.5));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
kernel void k_sample_int(texture2d<int, access::sample> t [[texture(0)]], sampler s [[sampler(0)]], device int* out [[buffer(0)]]) {
    int4 v = t.sample(s, float2(0.5, 0.5));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
kernel void k_sample_depth(depth2d<float, access::sample> t [[texture(0)]], sampler s [[sampler(0)]], device float* out [[buffer(0)]]) {
    float v = t.sample(s, float2(0.5, 0.5));
    out[0] = v; out[1] = 0; out[2] = 0; out[3] = 0;
}

// ---------------------------------------------------------------- storage_read (access::read)
kernel void k_read_float(texture2d<float, access::read> t [[texture(0)]], device float* out [[buffer(0)]]) {
    float4 v = t.read(uint2(0, 0));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
kernel void k_read_uint(texture2d<uint, access::read> t [[texture(0)]], device uint* out [[buffer(0)]]) {
    uint4 v = t.read(uint2(0, 0));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}
kernel void k_read_int(texture2d<int, access::read> t [[texture(0)]], device int* out [[buffer(0)]]) {
    int4 v = t.read(uint2(0, 0));
    out[0] = v.x; out[1] = v.y; out[2] = v.z; out[3] = v.w;
}

// ---------------------------------------------------------------- storage_write (access::write)
kernel void k_write_float(texture2d<float, access::write> t [[texture(0)]], constant float4& v [[buffer(0)]]) {
    t.write(v, uint2(0, 0));
}
kernel void k_write_uint(texture2d<uint, access::write> t [[texture(0)]], constant uint4& v [[buffer(0)]]) {
    t.write(v, uint2(0, 0));
}
kernel void k_write_int(texture2d<int, access::write> t [[texture(0)]], constant int4& v [[buffer(0)]]) {
    t.write(v, uint2(0, 0));
}

// ---------------------------------------------------------------- atomic (access::read_write, uint/int kind only -- MSL provides no texture atomics on non-integer element types, an MSL-language fact, not tested per-format)
kernel void k_atomic_uint(texture2d<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
    uint4 prev = t.atomic_fetch_add(uint2(0, 0), uint4(7, 0, 0, 0));
    uint4 now = t.read(uint2(0, 0));
    out[0] = prev.x; out[1] = now.x;
}
kernel void k_atomic_int(texture2d<int, access::read_write> t [[texture(0)]], device int* out [[buffer(0)]]) {
    int4 prev = t.atomic_fetch_add(uint2(0, 0), int4(7, 0, 0, 0));
    int4 now = t.read(uint2(0, 0));
    out[0] = prev.x; out[1] = now.x;
}

// ---------------------------------------------------------------- render pipeline: fullscreen triangle covering a 16x16 target
struct VOut { float4 position [[position]]; };
vertex VOut vs_fullscreen(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-1, -1), float2(3, -1), float2(-1, 3) };
    VOut o; o.position = float4(pos[vid], 0.5, 1.0); return o;
}
// Depth-attachment probes need a controllable depth; z is passed as a buffer constant so the
// same vertex function serves both the plain color-only draws (renderable/blendable/msaa/resolve,
// z=0.5 is irrelevant with no depth attachment bound) and the depth_stencil draws (z chosen to
// straddle a known depth-compare reference).
vertex VOut vs_fullscreen_z(uint vid [[vertex_id]], constant float& z [[buffer(0)]]) {
    float2 pos[3] = { float2(-1, -1), float2(3, -1), float2(-1, 3) };
    VOut o; o.position = float4(pos[vid], z, 1.0); return o;
}
fragment float4 fs_color_float(VOut in [[stage_in]]) { return float4(0.25, 0.5, 0.75, 1.0); }
fragment uint4 fs_color_uint(VOut in [[stage_in]]) { return uint4(3, 5, 7, 1); }
fragment int4 fs_color_int(VOut in [[stage_in]]) { return int4(-3, 5, -7, 1); }
fragment void fs_depth_only(VOut in [[stage_in]]) {}
