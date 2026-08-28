#include <metal_stdlib>
using namespace metal;
// D6: genuine ORIGINAL uncovered helper via partial primitive coverage (not
// discard). A diagonal-edge triangle covering roughly the left half of the target
// creates quads straddling the edge, whose right-of-edge pixels are original
// (never-covered) helper invocations. Records is_helper and a fwidth() read using
// the same schema as the demoted-lane probes for direct comparison.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p;
    if (vid == 0)      p = float2(-1.0, -1.0);
    else if (vid == 1) p = float2(-1.0,  1.0);
    else               p = float2( 0.0,  1.0);
    VOut o; o.pos = float4(p, 0.0, 1.0); return o;
}
struct Rec { uint marker; uint fwidth_bits; uint is_helper_pre; uint is_helper_post; };
fragment float4 f_main(float4 pos [[position]],
                        device Rec *out [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    bool helper_pre = simd_is_helper_thread();
    float fw = fwidth(pos.x);
    bool helper_post = simd_is_helper_thread();
    out[idx].marker = idx + 1u;
    out[idx].fwidth_bits = as_type<uint>(fw);
    out[idx].is_helper_pre = helper_pre ? 1u : 0u;
    out[idx].is_helper_post = helper_post ? 1u : 0u;
    return float4(0.75, 0.5, 0.25, 1.0);
}
