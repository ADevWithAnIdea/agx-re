#include <metal_stdlib>
using namespace metal;
kernel void k_min1(device uint* out [[buffer(0)]],
                   device const uint* in [[buffer(1)]],
                   uint tid [[thread_position_in_grid]]) {
    out[tid] = in[tid] + 1u;
}
