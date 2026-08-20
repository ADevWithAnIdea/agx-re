// EXP-0062 complete authored MSL. Public typed render-store/read behavior only.
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 position [[position]]; };

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = vid == 0u ? float2(-1.0, -1.0) :
               vid == 1u ? float2( 3.0, -1.0) : float2(-1.0, 3.0);
    return { float4(p, 0.0, 1.0) };
}

fragment float4 f_rgba8unorm_edges(VOut in [[stage_in]]) {
    return float4(-0.25, 0.5, 1.25, 128.0 / 255.0);
}
fragment float4 f_bgra8unorm_edges(VOut in [[stage_in]]) {
    return float4(-0.25, 0.5, 1.25, 128.0 / 255.0);
}
fragment float4 f_rgba8srgb_threshold(VOut in [[stage_in]]) {
    return float4(0.0031308, 0.0031309, 0.5, 0.5);
}
fragment float4 f_r16unorm_midpoint(VOut in [[stage_in]]) {
    return float4(0.5, 0.0, 0.0, 1.0);
}
fragment float4 f_rgba16float_edges(VOut in [[stage_in]]) {
    return float4(-0.0, 1.0, 65504.0, 0.333251953125);
}
fragment uint f_r32uint_exact(VOut in [[stage_in]]) { return 0xdeadbeefu; }

kernel void k_read_float(texture2d<float, access::read> tex [[texture(0)]],
                         device uint4 *out [[buffer(0)]]) {
    out[0] = as_type<uint4>(tex.read(uint2(0, 0)));
}
kernel void k_read_uint(texture2d<uint, access::read> tex [[texture(0)]],
                        device uint4 *out [[buffer(0)]]) {
    uint4 v = tex.read(uint2(0, 0));
    out[0] = v;
}
