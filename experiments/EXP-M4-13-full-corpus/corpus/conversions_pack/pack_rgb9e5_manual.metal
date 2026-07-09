// conversions_pack: manual (OUR OWN) RGB9E5 shared-exponent float pack.
// Clean-room algorithm; surfaces max3/exponent-clamp/mul/convert chain used for
// shared-exponent packing (feature Metal does not expose as an intrinsic).
#include <metal_stdlib>
using namespace metal;
kernel void pack_rgb9e5_manual(device uint* o [[buffer(0)]],
                               device const float3* fa [[buffer(1)]],
                               uint i [[thread_position_in_grid]]) {
    float3 c = max(fa[i], float3(0.0f));
    float maxc = max(c.r, max(c.g, c.b));
    // exponent from the largest channel, clamped to the 5-bit shared field
    int e = clamp(int(ceil(log2(max(maxc, 1e-16f)))) + 1, 0, 31);
    float scale = exp2(float(9 - e - 15));   // mantissa scale
    uint3 m = uint3(clamp(round(c / scale), float3(0.0f), float3(511.0f)));
    o[i] = (uint(e) << 27) | (m.b << 18) | (m.g << 9) | m.r;
}
