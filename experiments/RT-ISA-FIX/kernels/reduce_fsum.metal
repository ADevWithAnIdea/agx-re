#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    float v = (float)lane;
    out[tid] = simd_sum(v);
}
