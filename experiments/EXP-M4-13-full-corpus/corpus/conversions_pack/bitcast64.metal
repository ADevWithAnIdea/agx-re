// conversions_pack: 64-bit as_type<> reinterpret across 8-byte types.
// Isolates float2<->ulong, uint2<->ulong, half4<->ulong repacks (64b moves).
#include <metal_stdlib>
using namespace metal;
kernel void bitcast64(device ulong* o [[buffer(0)]],
                      device const float2* f2 [[buffer(1)]],
                      device const uint2* u2 [[buffer(2)]],
                      device const half4* h4 [[buffer(3)]],
                      uint i [[thread_position_in_grid]]) {
    ulong  a = as_type<ulong>(f2[i]);    // 2x f32 -> u64
    ulong  b = as_type<ulong>(u2[i]);    // 2x u32 -> u64
    ulong  c = as_type<ulong>(h4[i]);    // 4x f16 -> u64
    float2 f = as_type<float2>(a);       // u64    -> 2x f32
    o[i] = a ^ b ^ c ^ as_type<ulong>(f);
}
