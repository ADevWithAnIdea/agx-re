#include <metal_stdlib>
using namespace metal;
kernel void k_min2(device uint* out [[buffer(0)]],
                   device const uint* in [[buffer(1)]],
                   uint tid [[thread_position_in_grid]]) {
    uint a = in[tid];
    uint b = in[tid+1];
    out[tid] = a*b + a;
}
