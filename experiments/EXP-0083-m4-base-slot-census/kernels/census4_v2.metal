#include <metal_stdlib>
using namespace metal;
// EXP-0083 census4 (authored; frozen): 4 MSL buffers (indices 0..3);
// gid-variant indices force the loads into the main program (a 4-buffer
// kernel with constant indices compiles to a single vector store whose
// loads all hoist into the constant program). gid==0 for the 1-thread
// dispatch, so b1[gid]=b1[0] and i0 = idxbuf[0] ^ 0 = 5.
kernel void census4(device uint* out [[buffer(0)]],
                   const device uint* b1 [[buffer(1)]],
                   const device uint* b2 [[buffer(2)]],
                   const device uint* idxbuf [[buffer(3)]],
                   uint gid [[thread_position_in_grid]]) {
    uint i0 = idxbuf[0] ^ (gid & 0xF0u);
    out[1] = b1[gid];
    out[2] = b2[gid];
    out[3] = i0;
    out[0] = b2[i0];
}
