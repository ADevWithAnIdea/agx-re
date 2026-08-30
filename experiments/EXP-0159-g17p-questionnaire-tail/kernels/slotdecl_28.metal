// EXP-0159 FE probe: 28 declared device-buffer arguments (MEM-19).
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
              device const uint* b25 [[buffer(25)]],
              device const uint* b26 [[buffer(26)]],
              device const uint* b27 [[buffer(27)]],
              device const uint* b28 [[buffer(28)]],
              uint gid [[thread_position_in_grid]]) {
  out[gid] = b1[gid]^b2[gid]^b3[gid]^b4[gid]^b5[gid]^b6[gid]^b7[gid]^b8[gid]^b9[gid]^b10[gid]^b11[gid]^b12[gid]^b13[gid]^b14[gid]^b15[gid]^b16[gid]^b17[gid]^b18[gid]^b19[gid]^b20[gid]^b21[gid]^b22[gid]^b23[gid]^b24[gid]^b25[gid]^b26[gid]^b27[gid]^b28[gid];
}
