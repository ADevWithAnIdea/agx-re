// conversions_pack: unpack_(un/s)norm intrinsics to float AND to half.
// Isolates unorm4x8/snorm4x8/unorm2x16/snorm2x16 unpack -> float4/2, and ->half variants.
#include <metal_stdlib>
using namespace metal;
kernel void unpack_norm(device float* o [[buffer(0)]],
                        device const uint* ua [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    uint u = ua[i];
    float4 a = unpack_unorm4x8_to_float(u);
    float4 b = unpack_snorm4x8_to_float(u);
    float2 c = unpack_unorm2x16_to_float(u);
    float2 d = unpack_snorm2x16_to_float(u);
    half4  e = unpack_unorm4x8_to_half(u);
    half4  g = unpack_snorm4x8_to_half(u);
    half2  k = unpack_unorm2x16_to_half(u);
    half2  m = unpack_snorm2x16_to_half(u);
    o[i] = a.x + b.y + c.x + d.y + float(e.z) + float(g.w) + float(k.x) + float(m.y);
}
