#include <metal_stdlib>
using namespace metal;
// EXP-0084 generated (frozen; authored generator: gen_cap_kernels.py).
// MEM-22 direct-slot-count boundary probe: cap31 = the known-working 31-
// buffer-argument configuration (indices 0..30, replicating the shape of
// EXP-0078's non-promoted capacity.metal hypothesis, independently re-
// established here); cap32 extends by exactly one buffer argument (indices
// 0..31) to test the MSL compile-time direct-argument-count boundary. Each
// output element is one directly-bound buffer's own tag word -- no cross-
// buffer aliasing is possible if every out[k-1] independently equals bk[0].

kernel void cap31(
    device uint* out [[buffer(0)]],
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
    const device uint* b30 [[buffer(30)]]
) {
    out[0] = b1[0];
    out[1] = b2[0];
    out[2] = b3[0];
    out[3] = b4[0];
    out[4] = b5[0];
    out[5] = b6[0];
    out[6] = b7[0];
    out[7] = b8[0];
    out[8] = b9[0];
    out[9] = b10[0];
    out[10] = b11[0];
    out[11] = b12[0];
    out[12] = b13[0];
    out[13] = b14[0];
    out[14] = b15[0];
    out[15] = b16[0];
    out[16] = b17[0];
    out[17] = b18[0];
    out[18] = b19[0];
    out[19] = b20[0];
    out[20] = b21[0];
    out[21] = b22[0];
    out[22] = b23[0];
    out[23] = b24[0];
    out[24] = b25[0];
    out[25] = b26[0];
    out[26] = b27[0];
    out[27] = b28[0];
    out[28] = b29[0];
    out[29] = b30[0];
}

kernel void cap32(
    device uint* out [[buffer(0)]],
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
    const device uint* b30 [[buffer(30)]],
    const device uint* b31 [[buffer(31)]]
) {
    out[0] = b1[0];
    out[1] = b2[0];
    out[2] = b3[0];
    out[3] = b4[0];
    out[4] = b5[0];
    out[5] = b6[0];
    out[6] = b7[0];
    out[7] = b8[0];
    out[8] = b9[0];
    out[9] = b10[0];
    out[10] = b11[0];
    out[11] = b12[0];
    out[12] = b13[0];
    out[13] = b14[0];
    out[14] = b15[0];
    out[15] = b16[0];
    out[16] = b17[0];
    out[17] = b18[0];
    out[18] = b19[0];
    out[19] = b20[0];
    out[20] = b21[0];
    out[21] = b22[0];
    out[22] = b23[0];
    out[23] = b24[0];
    out[24] = b25[0];
    out[25] = b26[0];
    out[26] = b27[0];
    out[27] = b28[0];
    out[28] = b29[0];
    out[29] = b30[0];
    out[30] = b31[0];
}

