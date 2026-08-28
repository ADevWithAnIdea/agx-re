#include <metal_stdlib>
using namespace metal;
// D4: implicit-LOD texture sample after a partial-quad discard. Even-x lanes
// discard, then (after the branch) ALL lanes sample a mip-mapped checker texture
// with implicit LOD using a coordinate that depends on fragcoord (so quad
// derivatives determine the selected LOD). Surviving (odd-x) lane's sampled color
// is recorded; compared against a no-discard control (d_control_tex.metal) to see
// whether LOD selection for the survivor is affected by its discarded neighbor.
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
    bool killme = (px & 1u) == 0u;
    bool helper_pre = simd_is_helper_thread();
    float2 uv = pos.xy * 0.25;
    if (killme) {
        discard_fragment();
        uv = uv * 37.0;   // large post-discard perturbation to the sample coordinate
    }
    bool helper_post = simd_is_helper_thread();
    float4 s = tex.sample(smp, uv);
    out[idx].marker = idx + 1u;
    out[idx].sampled_bits = as_type<uint>(s.r);
    out[idx].is_helper_pre = helper_pre ? 1u : 0u;
    out[idx].is_helper_post = helper_post ? 1u : 0u;
    return s;
}
