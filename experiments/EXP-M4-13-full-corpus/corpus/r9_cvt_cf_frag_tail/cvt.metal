#include <metal_stdlib>
using namespace metal;

// ---- cvt_i2f (int->float) single-toggle variants ----

// baseline signed int32 -> float32
kernel void i2f_s32(device float* o, device int* a, uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
// toggle: unsigned source (signflag / src_class)
kernel void i2f_u32(device float* o, device uint* a, uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
// toggle: 16-bit source width (short)
kernel void i2f_s16(device float* o, device short* a, uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
kernel void i2f_u16(device float* o, device ushort* a, uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
// toggle: 8-bit source width (char)
kernel void i2f_s8(device float* o, device char* a, uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
kernel void i2f_u8(device float* o, device uchar* a, uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
// toggle: dst is half (int -> half)
kernel void i2h_s32(device half* o, device int* a, uint i [[thread_position_in_grid]]) {
    o[i] = half(a[i]);
}
kernel void i2h_u32(device half* o, device uint* a, uint i [[thread_position_in_grid]]) {
    o[i] = half(a[i]);
}

// DST/SRC register stepping: a chain of independent conversions.
// Each conversion reads a distinct loaded source and writes a distinct output slot,
// so successive cvt_i2f instructions should step their dst-desc and src-reg fields.
kernel void i2f_chain(device float4* o, device int4* a, uint i [[thread_position_in_grid]]) {
    int4 v = a[i];
    float x0 = float(v.x);
    float x1 = float(v.y);
    float x2 = float(v.z);
    float x3 = float(v.w);
    o[i] = float4(x0, x1, x2, x3);
}

// ---- cvt_f2i (float->int) single-toggle variants ----
kernel void f2i_s32(device int* o, device float* a, uint i [[thread_position_in_grid]]) {
    o[i] = int(a[i]);
}
kernel void f2i_u32(device uint* o, device float* a, uint i [[thread_position_in_grid]]) {
    o[i] = uint(a[i]);
}
// 16-bit dest width
kernel void f2i_s16(device short* o, device float* a, uint i [[thread_position_in_grid]]) {
    o[i] = short(a[i]);
}
kernel void f2i_u16(device ushort* o, device float* a, uint i [[thread_position_in_grid]]) {
    o[i] = ushort(a[i]);
}
// 8-bit dest width
kernel void f2i_s8(device char* o, device float* a, uint i [[thread_position_in_grid]]) {
    o[i] = char(a[i]);
}
kernel void f2i_u8(device uchar* o, device float* a, uint i [[thread_position_in_grid]]) {
    o[i] = uchar(a[i]);
}
// half source
kernel void h2i_s32(device int* o, device half* a, uint i [[thread_position_in_grid]]) {
    o[i] = int(a[i]);
}
kernel void h2i_u32(device uint* o, device half* a, uint i [[thread_position_in_grid]]) {
    o[i] = uint(a[i]);
}
// DST/SRC register stepping for f2i
kernel void f2i_chain(device int4* o, device float4* a, uint i [[thread_position_in_grid]]) {
    float4 v = a[i];
    int y0 = int(v.x);
    int y1 = int(v.y);
    int y2 = int(v.z);
    int y3 = int(v.w);
    o[i] = int4(y0, y1, y2, y3);
}

// DISAMBIGUATION: reversed lane order. Result lane x reads source v.w, etc.
// If byte+3 tracks DEST it stays 0,2,4,6; if it tracks SOURCE it goes 6,4,2,0.
kernel void i2f_rev(device float4* o, device int4* a, uint i [[thread_position_in_grid]]) {
    int4 v = a[i];
    o[i] = float4(float(v.w), float(v.z), float(v.y), float(v.x));
}
kernel void f2i_rev(device int4* o, device float4* a, uint i [[thread_position_in_grid]]) {
    float4 v = a[i];
    o[i] = int4(int(v.w), int(v.z), int(v.y), int(v.x));
}
