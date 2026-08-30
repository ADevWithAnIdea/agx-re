// EXP-0159 FE carrier (MEM-19). Authored by the clean-room RE team.
// 31 device buffers bound simultaneously (the public per-stage maximum).
// Buffer 0 is the output; buffers 1..30 each carry a distinctive identifying
// word 0x51000000|k. One probe device_load whose base_slot byte is spliced
// tells us which binding the selector actually landed on.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              device const uint* b1 [[buffer(1)]],  device const uint* b2 [[buffer(2)]],
              device const uint* b3 [[buffer(3)]],  device const uint* b4 [[buffer(4)]],
              device const uint* b5 [[buffer(5)]],  device const uint* b6 [[buffer(6)]],
              device const uint* b7 [[buffer(7)]],  device const uint* b8 [[buffer(8)]],
              device const uint* b9 [[buffer(9)]],  device const uint* b10 [[buffer(10)]],
              device const uint* b11 [[buffer(11)]], device const uint* b12 [[buffer(12)]],
              device const uint* b13 [[buffer(13)]], device const uint* b14 [[buffer(14)]],
              device const uint* b15 [[buffer(15)]], device const uint* b16 [[buffer(16)]],
              device const uint* b17 [[buffer(17)]], device const uint* b18 [[buffer(18)]],
              device const uint* b19 [[buffer(19)]], device const uint* b20 [[buffer(20)]],
              device const uint* b21 [[buffer(21)]], device const uint* b22 [[buffer(22)]],
              device const uint* b23 [[buffer(23)]], device const uint* b24 [[buffer(24)]],
              device const uint* b25 [[buffer(25)]], device const uint* b26 [[buffer(26)]],
              device const uint* b27 [[buffer(27)]], device const uint* b28 [[buffer(28)]],
              device const uint* b29 [[buffer(29)]], device const uint* b30 [[buffer(30)]],
              uint gid [[thread_position_in_grid]]) {
  // The probe: a single load from b17, which the splice re-points.
  uint probe = b17[0];
  // Keep every other binding live so all 31 base slots are really populated
  // (a dead binding would be optimised out and its slot never written).
  uint acc = b1[0]^b2[0]^b3[0]^b4[0]^b5[0]^b6[0]^b7[0]^b8[0]^b9[0]^b10[0]
           ^ b11[0]^b12[0]^b13[0]^b14[0]^b15[0]^b16[0]^b18[0]^b19[0]^b20[0]
           ^ b21[0]^b22[0]^b23[0]^b24[0]^b25[0]^b26[0]^b27[0]^b28[0]^b29[0]^b30[0];
  out[0] = probe;
  out[1] = acc;
  out[2] = gid;
}
