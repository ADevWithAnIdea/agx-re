// conversions_pack: vector as_type<> reinterpret across lane counts (same total bits).
// Isolates half2<->uint, uchar4<->uint, float4<->uint4, half4<->uint2 repacks.
#include <metal_stdlib>
using namespace metal;
kernel void bitcast_vec(device uint* o [[buffer(0)]],
                        device const half2* h2 [[buffer(1)]],
                        device const uchar4* c4 [[buffer(2)]],
                        device const float4* f4 [[buffer(3)]],
                        device const half4* h4 [[buffer(4)]],
                        uint i [[thread_position_in_grid]]) {
    uint  a = as_type<uint>(h2[i]);      // 2x f16 -> u32
    uint  b = as_type<uint>(c4[i]);      // 4x u8  -> u32
    half2 hb = as_type<half2>(b);        // u32    -> 2x f16
    uint4 v = as_type<uint4>(f4[i]);     // 4x f32 -> 4x u32
    uint2 w = as_type<uint2>(h4[i]);     // 4x f16 -> 2x u32
    o[i] = a ^ b ^ as_type<uint>(hb) ^ v.x ^ v.y ^ v.z ^ v.w ^ w.x ^ w.y;
}
