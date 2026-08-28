#include <metal_stdlib>
using namespace metal;
// Control for d_tex_implicit_lod.metal: identical texture sample, no discard, no
// coordinate perturbation.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct Rec { uint marker; uint sampled_bits; uint is_helper_pre; uint is_helper_post; };
fragment float4 f_main(float4 pos [[position]],
                        texture2d<float> tex [[texture(0)]],
                        sampler smp [[sampler(0)]],
                        device Rec *out [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    bool helper_pre = simd_is_helper_thread();
    float2 uv = pos.xy * 0.25;
    bool helper_post = simd_is_helper_thread();
    float4 s = tex.sample(smp, uv);
    out[idx].marker = idx + 1u;
    out[idx].sampled_bits = as_type<uint>(s.r);
    out[idx].is_helper_pre = helper_pre ? 1u : 0u;
    out[idx].is_helper_post = helper_post ? 1u : 0u;
    return s;
}
