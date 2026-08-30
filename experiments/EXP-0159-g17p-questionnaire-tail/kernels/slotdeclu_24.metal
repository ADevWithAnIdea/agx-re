// EXP-0159 FE probe: 24 declared device-buffer arguments, read UNIFORMLY (MEM-19).
// Authored by the clean-room RE team.  Uniform (thread-invariant) reads are
// exactly the ones the compiler hoists into _agc.main.constant_program -- the
// USC constant/uniform program -- so this variant measures how many base slots
// that program actually preloads, as a function of the binding count.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              device const uint* b1 [[buffer(1)]],
              device const uint* b2 [[buffer(2)]],
              device const uint* b3 [[buffer(3)]],
              device const uint* b4 [[buffer(4)]],
              device const uint* b5 [[buffer(5)]],
              device const uint* b6 [[buffer(6)]],
              device const uint* b7 [[buffer(7)]],
              device const uint* b8 [[buffer(8)]],
              device const uint* b9 [[buffer(9)]],
              device const uint* b10 [[buffer(10)]],
              device const uint* b11 [[buffer(11)]],
              device const uint* b12 [[buffer(12)]],
              device const uint* b13 [[buffer(13)]],
              device const uint* b14 [[buffer(14)]],
              device const uint* b15 [[buffer(15)]],
              device const uint* b16 [[buffer(16)]],
              device const uint* b17 [[buffer(17)]],
              device const uint* b18 [[buffer(18)]],
              device const uint* b19 [[buffer(19)]],
              device const uint* b20 [[buffer(20)]],
              device const uint* b21 [[buffer(21)]],
              device const uint* b22 [[buffer(22)]],
              device const uint* b23 [[buffer(23)]],
              device const uint* b24 [[buffer(24)]],
              uint gid [[thread_position_in_grid]]) {
  out[gid] = b1[0]^b2[0]^b3[0]^b4[0]^b5[0]^b6[0]^b7[0]^b8[0]^b9[0]^b10[0]^b11[0]^b12[0]^b13[0]^b14[0]^b15[0]^b16[0]^b17[0]^b18[0]^b19[0]^b20[0]^b21[0]^b22[0]^b23[0]^b24[0];
}
