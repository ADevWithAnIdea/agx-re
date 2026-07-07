#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane*10u + 5u;
    out[tid] = simd_shuffle_xor(v, 3);
}
