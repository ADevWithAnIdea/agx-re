#include <metal_stdlib>
using namespace metal;
// Two independently-controlled index candidates i0,i1 (from idxbuf).
// The load into a[] uses i0; i1 is kept live by storing it to out2.
// So splicing the load's index-register selector from i0's reg to i1's reg
// switches the observed read from a[i0] to a[i1].
kernel void k(device uint* out  [[buffer(0)]],
              device uint* out2 [[buffer(1)]],
              const device uint* a      [[buffer(2)]],
              const device uint* idxbuf [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    uint i0 = idxbuf[2*gid + 0];
    uint i1 = idxbuf[2*gid + 1];
    out[gid]  = a[i0];
    out2[gid] = i1;
}
