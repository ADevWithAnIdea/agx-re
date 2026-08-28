#include <metal_stdlib>
using namespace metal;
// D1 control: no discard anywhere. Records fwidth(uv) where uv = fragcoord.xy (a
// hardware-smooth per-pixel gradient with a KNOWN derivative of exactly 1.0 in x and
// y for an axis-aligned full-screen triangle) into buffer(0), one uint2-packed record
// per pixel: [0]=marker(pixel id), [1]=bitcast(fwidth.x). No mutation, no discard.
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
    bool helper_pre = simd_is_helper_thread();
    // no discard here
    bool helper_post = simd_is_helper_thread();
    float fw = fwidth(uv.x);
    out[idx].marker = idx + 1u;
    out[idx].fwidth_bits = as_type<uint>(fw);
    out[idx].is_helper_pre = helper_pre ? 1u : 0u;
    out[idx].is_helper_post = helper_post ? 1u : 0u;
    return float4(0.75, 0.5, 0.25, 1.0);
}
