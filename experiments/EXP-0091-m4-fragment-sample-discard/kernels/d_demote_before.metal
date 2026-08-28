#include <metal_stdlib>
using namespace metal;
// D2: even-x lanes call discard_fragment() and THEN, only in that branch, add a
// large perturbation (+1000) to a local copy of the position-derived coordinate.
// fwidth() is computed AFTER the branch merge from the (possibly perturbed) value,
// by every lane (odd-x lanes survive and write the result). If Apple9 gives
// discard SPIR-V-demote semantics (helper lane keeps executing straight-line code,
// including the +1000 mutation), the surviving neighbor's fwidth() will reflect the
// perturbation (blown up vs the D1 control). If discard is a true terminate, the
// mutation never executes and fwidth() matches the D1 control exactly.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct Rec { uint marker; uint fwidth_bits; uint is_helper_pre; uint is_helper_post; };
fragment float4 f_main(float4 pos [[position]],
                        device Rec *out [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    float2 uv = pos.xy;
    bool killme = (px & 1u) == 0u;
    bool helper_pre = simd_is_helper_thread();
    if (killme) {
        discard_fragment();
        uv = uv + float2(1000.0, 1000.0);
    }
    bool helper_post = simd_is_helper_thread();
    float fw = fwidth(uv.x);
    out[idx].marker = idx + 1u;
    out[idx].fwidth_bits = as_type<uint>(fw);
    out[idx].is_helper_pre = helper_pre ? 1u : 0u;
    out[idx].is_helper_post = helper_post ? 1u : 0u;
    return float4(0.75, 0.5, 0.25, 1.0);
}
