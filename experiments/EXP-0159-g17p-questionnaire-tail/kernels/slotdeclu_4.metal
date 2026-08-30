// EXP-0159 FE probe: 4 declared device-buffer arguments, read UNIFORMLY (MEM-19).
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
              uint gid [[thread_position_in_grid]]) {
  out[gid] = b1[0]^b2[0]^b3[0]^b4[0];
}
