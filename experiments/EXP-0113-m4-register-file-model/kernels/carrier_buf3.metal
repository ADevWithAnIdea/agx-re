// EXP-0113 H3 buffer-signature carrier, 3-buffer variant. OWN MSL.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              device float* mem2 [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid] = mem[tid] + mem2[tid] + 1.0;
}
