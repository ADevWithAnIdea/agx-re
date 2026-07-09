#include <metal_stdlib>
using namespace metal;
// Four simultaneous zero-extends -> four live dst regs (dst-reg sweep).
kernel void k_zext4(device uint4* o [[buffer(0)]], device const ushort* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    uint x0=(uint)a[4*t+0], x1=(uint)a[4*t+1], x2=(uint)a[4*t+2], x3=(uint)a[4*t+3];
    o[t]=uint4(x0,x1,x2,x3);
}
// eight simultaneous -> push regs higher
kernel void k_zext8w(device uint* o [[buffer(0)]], device const ushort* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    uint s=0;
    for (uint i=0;i<8;i++){ uint x=(uint)a[8*t+i]; o[8*t+i]=x; s+=x; }
    o[8*t]=s;
}
// zero-extend of a value that comes from an ADD (source = a computed reg, not a load)
kernel void k_zext_src(device uint* o [[buffer(0)]], device const ushort* a [[buffer(1)]], device const ushort* b [[buffer(2)]], uint t [[thread_position_in_grid]]) {
    ushort v = a[t] + b[t];
    o[t] = (uint)v;
}
// two different sources zero-extended and both stored
kernel void k_zext_twosrc(device uint2* o [[buffer(0)]], device const ushort* a [[buffer(1)]], device const ushort* b [[buffer(2)]], uint t [[thread_position_in_grid]]) {
    o[t] = uint2((uint)a[t], (uint)b[t]);
}
