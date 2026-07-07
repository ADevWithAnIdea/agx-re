#include <metal_stdlib>
using namespace metal;
// a[] is an identity ramp so out = (index actually used) directly.
// i0 is the load index; i1,i2,i3 are kept live (distinct known values) so a
// sweep of the load's index-register selector reveals which register is used.
kernel void k(device uint* out  [[buffer(0)]],
              device uint* out2 [[buffer(1)]],
              const device uint* a      [[buffer(2)]],
              const device uint* idxbuf [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    uint i0 = idxbuf[gid*4 + 0];
    uint i1 = idxbuf[gid*4 + 1];
    uint i2 = idxbuf[gid*4 + 2];
    uint i3 = idxbuf[gid*4 + 3];
    out[gid]  = a[i0];
    out2[gid] = i1 + (i2<<8) + (i3<<16);
}
