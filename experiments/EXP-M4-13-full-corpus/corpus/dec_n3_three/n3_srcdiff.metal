#include <metal_stdlib>
using namespace metal;
kernel void ksrc0(device uint* o [[buffer(0)]], device const ushort* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    o[t]=(uint)a[t];
}
kernel void ksrc1(device uint* o [[buffer(0)]], device const ushort* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    uint keep = (uint)a[2*t] + 7u;     // stays live in a reg
    uint v = (uint)a[2*t+1];           // the zext to diff
    o[t]=v; o[t+128]=keep;
}
kernel void ksrc2(device uint* o [[buffer(0)]], device const ushort* a [[buffer(1)]], uint t [[thread_position_in_grid]]) {
    uint k0=(uint)a[3*t]+1u, k1=(uint)a[3*t+1]+2u;  // two live regs before the zext
    uint v=(uint)a[3*t+2];
    o[t]=v; o[t+128]=k0; o[t+256]=k1;
}
