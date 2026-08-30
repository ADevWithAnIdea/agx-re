// EXP-0159 FE probe: 2 declared device-buffer arguments (MEM-19).
// Authored by the clean-room RE team.  Each binding is read through a
// thread-varying index so none can be folded away; the point is to make
// the USC constant/uniform program populate one base slot per binding.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              device const uint* b1 [[buffer(1)]],
              device const uint* b2 [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  out[gid] = b1[gid]^b2[gid];
}
