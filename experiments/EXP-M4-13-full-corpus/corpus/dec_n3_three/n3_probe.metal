#include <metal_stdlib>
using namespace metal;

// Zero-extend ushort->uint (the documented mov_zext16 construct). Multiple
// independent extends to push results into different destination registers.
kernel void k_zext1(device uint* o [[buffer(0)]], device const ushort* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    o[t] = (uint)a[t];
}
kernel void k_zext_many(device uint* o [[buffer(0)]], device const ushort* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    uint r0 = (uint)a[t+0];
    uint r1 = (uint)a[t+1];
    uint r2 = (uint)a[t+2];
    uint r3 = (uint)a[t+3];
    o[t] = r0 ^ (r1<<1) ^ (r2<<2) ^ (r3<<3);
}
// sign-extend short->int for contrast
kernel void k_sext(device int* o [[buffer(0)]], device const short* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    o[t] = (int)a[t];
}
// zero-extend uchar->uint (8-bit)
kernel void k_zext8(device uint* o [[buffer(0)]], device const uchar* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    o[t] = (uint)a[t];
}
// narrow uint->ushort (truncate) then store as ushort
kernel void k_narrow(device ushort* o [[buffer(0)]], device const uint* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    o[t] = (ushort)a[t];
}
// bitwise AND with 0xffff (explicit mask, should equal zext16)
kernel void k_mask16(device uint* o [[buffer(0)]], device const uint* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    o[t] = a[t] & 0xffffu;
}
