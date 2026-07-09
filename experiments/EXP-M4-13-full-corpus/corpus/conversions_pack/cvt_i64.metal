// conversions_pack: 64-bit integer conversions & sign/zero extension.
// Isolates i32->i64 (sign-ext), u32->u64 (zero-ext), i64->i32 (trunc), i64<->f32.
#include <metal_stdlib>
using namespace metal;
kernel void cvt_i64(device long* o [[buffer(0)]],
                    device const int* ia [[buffer(1)]],
                    device const uint* ua [[buffer(2)]],
                    device const long* la [[buffer(3)]],
                    uint i [[thread_position_in_grid]]) {
    int  n = ia[i];
    uint u = ua[i];
    long L = la[i];
    long  a = long(n);           // i32 -> i64 sign-extend
    long  b = long(u);           // u32 -> i64 zero-extend
    ulong c = ulong(n);          // i32 -> u64
    int   d = int(L);            // i64 -> i32 truncate
    float e = float(L);          // i64 -> f32
    long  g = long(e);           // f32 -> i64
    o[i] = a + b + long(c) + long(d) + long(e) + g;
}
