// EXP-0159 FE probe: 16 declared device-buffer arguments, read UNIFORMLY (MEM-19).
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
              uint gid [[thread_position_in_grid]]) {
  out[gid] = b1[0]^b2[0]^b3[0]^b4[0]^b5[0]^b6[0]^b7[0]^b8[0]^b9[0]^b10[0]^b11[0]^b12[0]^b13[0]^b14[0]^b15[0]^b16[0];
}
