// conversions_pack: integer -> float/half numeric conversions.
// Isolates {i32,u32,i16,u8} -> f32 and i32/u32 -> f16 convert opcodes.
#include <metal_stdlib>
using namespace metal;
kernel void cvt_i2f(device float* o [[buffer(0)]],
                    device const int* ia [[buffer(1)]],
                    device const uint* ua [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    int  n = ia[i];
    uint u = ua[i];
    float a = float(n);          // i32 -> f32
    float b = float(u);          // u32 -> f32
    half  c = half(n);           // i32 -> f16
    half  d = half(u);           // u32 -> f16
    float e = float(short(n));   // i16 -> f32
    float g = float(uchar(u));   // u8  -> f32
    o[i] = a + b + float(c) + float(d) + e + g;
}
