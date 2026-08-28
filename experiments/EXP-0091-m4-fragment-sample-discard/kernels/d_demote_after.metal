#include <metal_stdlib>
using namespace metal;
// D3: same as D2 but discard_fragment() is placed AFTER fwidth() is computed (so
// the derivative read happens before any lane could have terminated). Control for
// statement-order sensitivity -- must show the *unperturbed* baseline value on the
// killed lane's own record (which will be write-suppressed if it's the discarded
// one) and on survivors (unaffected either way since the mutation never exists in
// this variant).
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
    float fw = fwidth(uv.x);
    if (killme) {
        discard_fragment();
        uv = uv + float2(1000.0, 1000.0);
    }
    bool helper_post = simd_is_helper_thread();
    out[idx].marker = idx + 1u;
    out[idx].fwidth_bits = as_type<uint>(fw);
    out[idx].is_helper_pre = helper_pre ? 1u : 0u;
    out[idx].is_helper_post = helper_post ? 1u : 0u;
    return float4(0.75, 0.5, 0.25, 1.0);
}
