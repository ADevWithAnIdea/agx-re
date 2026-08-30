// EXP-0159 FE probe: 8 declared device-buffer arguments (MEM-19).
// Authored by the clean-room RE team.  Each binding is read through a
// thread-varying index so none can be folded away; the point is to make
// the USC constant/uniform program populate one base slot per binding.
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
              uint gid [[thread_position_in_grid]]) {
  out[gid] = b1[gid]^b2[gid]^b3[gid]^b4[gid]^b5[gid]^b6[gid]^b7[gid]^b8[gid];
}
