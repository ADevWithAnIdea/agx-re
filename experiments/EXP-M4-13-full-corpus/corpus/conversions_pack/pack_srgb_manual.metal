// conversions_pack: manual (OUR OWN) linear->sRGB encode then unorm8 pack.
// Clean-room; surfaces the pow / compare-select / mul-add chain of gamma encode
// plus the unorm4x8 pack (Metal has no sRGB pack intrinsic).
#include <metal_stdlib>
using namespace metal;
static inline float lin2srgb(float c) {
    return select(1.055f * pow(c, 1.0f / 2.4f) - 0.055f, 12.92f * c, c <= 0.0031308f);
}
kernel void pack_srgb_manual(device uint* o [[buffer(0)]],
                             device const float4* fa [[buffer(1)]],
                             uint i [[thread_position_in_grid]]) {
    float4 c = saturate(fa[i]);
    float4 s = float4(lin2srgb(c.r), lin2srgb(c.g), lin2srgb(c.b), c.a);
    o[i] = pack_float_to_unorm4x8(s);
}
