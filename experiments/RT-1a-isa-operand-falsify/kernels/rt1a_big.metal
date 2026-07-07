#include <metal_stdlib>
using namespace metal;
// High register pressure + mixed fp16/fp32/int/int64 + deep nested expressions +
// broad ALU coverage (add/sub/mul/fma/min/max/div/sqrt/rsqrt/sin/exp/log/
// and/or/xor/shift/compare/popcount/clz/abs/select/int64).
kernel void big(device uint* out       [[buffer(0)]],
                const device float* F   [[buffer(1)]],
                const device int* I     [[buffer(2)]],
                const device uint* U    [[buffer(3)]],
                uint gid [[thread_position_in_grid]]) {
    // load a bank of distinct live values (forces many registers)
    float f[16]; int s[16]; uint u[16];
    for (int k=0;k<16;k++){ f[k]=F[gid*16+k]; s[k]=I[gid*16+k]; u[k]=U[gid*16+k]; }

    // deep-nested float expression tree using many ops
    float fa = (f[0]+f[1])*(f[2]-f[3]) + fma(f[4],f[5],f[6]);
    float fb = fmin(f[7],f[8]) + fmax(f[9],f[10]) + sqrt(fabs(f[11]));
    float fc = f[12]/(f[13]+1.0f) + rsqrt(fabs(f[14])+1.0f) + sin(f[15]);
    float fd = exp(f[0]*0.1f) + log(fabs(f[1])+1.0f) + f[2]*f[3]*f[4];
    float fr = fa*fb + fc - fd;

    // native half ops
    half h0 = half(f[5]); half h1 = half(f[6]);
    half hr = (h0+h1)*h0 - h1;
    fr += float(hr);

    // integer op tree: add/sub/mul/and/or/xor/shift/min/max/compare/popcount/clz
    int ia = (s[0]+s[1]) - (s[2]*s[3]);
    int ib = (s[4] & s[5]) | (s[6] ^ s[7]);
    int ic = (s[8] << 3) + (s[9] >> 2) + (s[10] % 7);
    int id = min(s[11], s[12]) + max(s[13], s[14]);
    uint ua = popcount(u[0]) + clz(u[1]) + (u[2] >> 1) + (u[3] & u[4]);
    int ie = (s[15] < s[0]) ? ia : ib;
    int ir = ia + ib + ic + id + ie + int(ua);

    // int64
    long la = long(s[0]) * long(s[1]) + long(s[2]);
    ulong lb = ulong(u[5]) + ulong(u[6]) * 0x100000000UL;
    ir += int(la ^ long(lb));

    out[gid] = uint(fr) ^ uint(ir) ^ u[7] ^ u[8] ^ u[9] ^ u[10] ^ u[11]
             ^ u[12] ^ u[13] ^ u[14] ^ u[15] ^ uint(s[15]);
}
