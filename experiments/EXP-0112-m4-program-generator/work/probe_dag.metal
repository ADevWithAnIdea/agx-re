#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              device int* imem [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid+0] = mem[tid+7];
    out[tid+1] = float(imem[tid+3]);
}
