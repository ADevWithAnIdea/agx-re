#include <metal_stdlib>
using namespace metal;
// EXP-0083 census31 (authored; frozen): 31 MSL buffers (indices 0..30).
// Every buffer word w of buffer k holds P(k,w) = 0xC0DE0000|(k<<8)|w (harness fill).
// out[0] is the PROBE load b1[i0] whose base_slot byte the census splices;
// out[1..29] are per-buffer witness reads; out[30] echoes i0.
kernel void census31(device uint* out [[buffer(0)]],
                   const device uint* b1 [[buffer(1)]],
                   const device uint* b2 [[buffer(2)]],
                   const device uint* b3 [[buffer(3)]],
                   const device uint* b4 [[buffer(4)]],
                   const device uint* b5 [[buffer(5)]],
                   const device uint* b6 [[buffer(6)]],
                   const device uint* b7 [[buffer(7)]],
                   const device uint* b8 [[buffer(8)]],
                   const device uint* b9 [[buffer(9)]],
                   const device uint* b10 [[buffer(10)]],
                   const device uint* b11 [[buffer(11)]],
                   const device uint* b12 [[buffer(12)]],
                   const device uint* b13 [[buffer(13)]],
                   const device uint* b14 [[buffer(14)]],
                   const device uint* b15 [[buffer(15)]],
                   const device uint* b16 [[buffer(16)]],
                   const device uint* b17 [[buffer(17)]],
                   const device uint* b18 [[buffer(18)]],
                   const device uint* b19 [[buffer(19)]],
                   const device uint* b20 [[buffer(20)]],
                   const device uint* b21 [[buffer(21)]],
                   const device uint* b22 [[buffer(22)]],
                   const device uint* b23 [[buffer(23)]],
                   const device uint* b24 [[buffer(24)]],
                   const device uint* b25 [[buffer(25)]],
                   const device uint* b26 [[buffer(26)]],
                   const device uint* b27 [[buffer(27)]],
                   const device uint* b28 [[buffer(28)]],
                   const device uint* b29 [[buffer(29)]],
                   const device uint* idxbuf [[buffer(30)]]) {
    uint i0 = idxbuf[0];
    out[1] = b1[0];
    out[2] = b2[0];
    out[3] = b3[0];
    out[4] = b4[0];
    out[5] = b5[0];
    out[6] = b6[0];
    out[7] = b7[0];
    out[8] = b8[0];
    out[9] = b9[0];
    out[10] = b10[0];
    out[11] = b11[0];
    out[12] = b12[0];
    out[13] = b13[0];
    out[14] = b14[0];
    out[15] = b15[0];
    out[16] = b16[0];
    out[17] = b17[0];
    out[18] = b18[0];
    out[19] = b19[0];
    out[20] = b20[0];
    out[21] = b21[0];
    out[22] = b22[0];
    out[23] = b23[0];
    out[24] = b24[0];
    out[25] = b25[0];
    out[26] = b26[0];
    out[27] = b27[0];
    out[28] = b28[0];
    out[29] = b29[0];
    out[30] = i0;
    out[0] = b1[i0];
}
