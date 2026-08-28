#include <metal_stdlib>
using namespace metal;
// EXP-0083 capacity (authored; frozen; never spliced): the MEM-15 direct
// method -- a kernel that independently reads a distinguishable value
// through every one of the 31 MSL buffer indices at once. gid-variant
// indices keep all loads in the main program (gid==0 => word 0 reads).
kernel void capacity(device uint* out [[buffer(0)]],
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
                   const device uint* idxbuf [[buffer(30)]],
                   uint gid [[thread_position_in_grid]]) {
    uint i0 = idxbuf[0] ^ (gid & 0xF0u);
    out[1] = b1[gid];
    out[2] = b2[gid];
    out[3] = b3[gid];
    out[4] = b4[gid];
    out[5] = b5[gid];
    out[6] = b6[gid];
    out[7] = b7[gid];
    out[8] = b8[gid];
    out[9] = b9[gid];
    out[10] = b10[gid];
    out[11] = b11[gid];
    out[12] = b12[gid];
    out[13] = b13[gid];
    out[14] = b14[gid];
    out[15] = b15[gid];
    out[16] = b16[gid];
    out[17] = b17[gid];
    out[18] = b18[gid];
    out[19] = b19[gid];
    out[20] = b20[gid];
    out[21] = b21[gid];
    out[22] = b22[gid];
    out[23] = b23[gid];
    out[24] = b24[gid];
    out[25] = b25[gid];
    out[26] = b26[gid];
    out[27] = b27[gid];
    out[28] = b28[gid];
    out[29] = b29[gid];
    out[30] = i0;
    out[0] = b1[i0];
}
