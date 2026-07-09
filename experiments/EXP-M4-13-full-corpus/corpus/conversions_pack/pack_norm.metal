// conversions_pack: pack_float_to_(un/s)norm intrinsics (normalized fixed-point pack).
// Isolates unorm4x8, snorm4x8, unorm2x16, snorm2x16 pack ops (float -> u32).
#include <metal_stdlib>
using namespace metal;
kernel void pack_norm(device uint* o [[buffer(0)]],
                      device const float4* f4 [[buffer(1)]],
                      device const float2* f2 [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    float4 v4 = f4[i];
    float2 v2 = f2[i];
    uint a = pack_float_to_unorm4x8(v4);
    uint b = pack_float_to_snorm4x8(v4);
    uint c = pack_float_to_unorm2x16(v2);
    uint d = pack_float_to_snorm2x16(v2);
    o[i] = a ^ b ^ c ^ d;
}
