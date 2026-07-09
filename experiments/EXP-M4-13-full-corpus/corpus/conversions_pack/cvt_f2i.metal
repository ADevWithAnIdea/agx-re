// conversions_pack: float -> integer numeric conversions (value-changing, trunc toward zero).
// Isolates f32 -> {i32,u32,i16,u16,i8,u8} narrowing convert opcodes.
#include <metal_stdlib>
using namespace metal;
kernel void cvt_f2i(device int* o [[buffer(0)]],
                    device const float* fa [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    float f = fa[i];
    int    a = int(f);       // f32 -> i32
    uint   b = uint(f);      // f32 -> u32
    short  c = short(f);     // f32 -> i16
    ushort e = ushort(f);    // f32 -> u16
    char   d = char(f);      // f32 -> i8
    uchar  g = uchar(f);     // f32 -> u8
    o[i] = a + int(b) + int(c) + int(e) + int(d) + int(g);
}
