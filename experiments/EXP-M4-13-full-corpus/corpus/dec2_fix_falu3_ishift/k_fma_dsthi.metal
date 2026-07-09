#include <metal_stdlib>
using namespace metal;
// Force MANY simultaneously-live fma results so the register allocator must use
// HIGH GPRs (>= r16). If byte0[4:8] is the dst reg LOW nibble, a dst >= 16 wraps
// byte0-hi (reg & 0xf) while byte+1 = (reg<<1)|size holds the full 7-bit reg.
kernel void k_fma_dsthi(device float* out [[buffer(0)]],
                        device const float* a [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    float acc[16];
    for (int i = 0; i < 16; ++i)
        acc[i] = fma(a[gid+i], a[gid+i+1], a[gid+i+2]);
    // keep all 16 live to the end
    float s = 0;
    for (int i = 0; i < 16; ++i) s += acc[i] * a[gid+i+3];
    out[gid] = s;
}
