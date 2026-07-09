// conversions_pack: 32-bit as_type<> bitcasts (reinterpret, no value change).
// Isolates float<->uint, float<->int, int<->uint reinterpret at 32b width.
#include <metal_stdlib>
using namespace metal;
kernel void bitcast32(device uint* o [[buffer(0)]],
                      device const float* fa [[buffer(1)]],
                      device const int* ia [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    float f = fa[i];
    int   n = ia[i];
    uint  a = as_type<uint>(f);          // f32 -> u32 reinterpret
    int   b = as_type<int>(f);           // f32 -> i32 reinterpret
    float c = as_type<float>(n);         // i32 -> f32 reinterpret
    uint  d = as_type<uint>(n);          // i32 -> u32 reinterpret (trivial)
    o[i] = a ^ uint(b) ^ as_type<uint>(c) ^ d;
}
