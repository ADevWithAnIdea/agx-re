#include <metal_stdlib>
using namespace metal;
// SUPPLEMENTARY (single-run, not in the frozen two-run gated matrix -- added after
// the frozen 78-case capture completed, to close a gap the frozen matrix's write-
// suppression finding revealed it could not answer directly): the discarded lane's
// OWN is_helper_pre/is_helper_post cannot be read via its own buffer write (GLFS-A06
// showed that write is suppressed), so relay it through quad_shuffle_xor into the
// surviving neighbor, which performs the actual write.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct Rec { uint marker; uint neighbor_helper_pre; uint neighbor_helper_post; uint own_helper_post; };
fragment float4 f_main(float4 pos [[position]],
                        device Rec *out [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    bool killme = (px & 1u) == 0u;
    uint helper_pre = simd_is_helper_thread() ? 1u : 0u;
    if (killme) discard_fragment();
    uint helper_post = simd_is_helper_thread() ? 1u : 0u;
    // quad_shuffle_xor(v,1) swaps within the 2x2 quad's x-pair, retrieving the
    // OTHER lane's (pre-discard-branch) computed value into this lane's register.
    uint neighbor_pre = quad_shuffle_xor(helper_pre, 1);
    uint neighbor_post = quad_shuffle_xor(helper_post, 1);
    out[idx].marker = idx + 1u;
    out[idx].neighbor_helper_pre = neighbor_pre;
    out[idx].neighbor_helper_post = neighbor_post;
    out[idx].own_helper_post = helper_post;
    return float4(0.75, 0.5, 0.25, 1.0);
}
