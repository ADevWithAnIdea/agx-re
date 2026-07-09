#include <metal_stdlib>
using namespace metal;
// Eight INDEPENDENT fma results live simultaneously -> allocator must use eight
// distinct dst registers. If byte0[4:8] is the dst-register field, the eight fma
// instructions carry eight distinct (typically incrementing) high nibbles.
kernel void k_fma_dst8(device float4* out [[buffer(0)]],
                       device const float* a [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    float s0 = fma(a[gid+0],  a[gid+1],  a[gid+2]);
    float s1 = fma(a[gid+3],  a[gid+4],  a[gid+5]);
    float s2 = fma(a[gid+6],  a[gid+7],  a[gid+8]);
    float s3 = fma(a[gid+9],  a[gid+10], a[gid+11]);
    float s4 = fma(a[gid+12], a[gid+13], a[gid+14]);
    float s5 = fma(a[gid+15], a[gid+16], a[gid+17]);
    float s6 = fma(a[gid+18], a[gid+19], a[gid+20]);
    float s7 = fma(a[gid+21], a[gid+22], a[gid+23]);
    out[2*gid+0] = float4(s0, s1, s2, s3);
    out[2*gid+1] = float4(s4, s5, s6, s7);
}
