#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    int v = (int)lane;
    out[tid] = simd_prefix_exclusive_sum(v);
}
