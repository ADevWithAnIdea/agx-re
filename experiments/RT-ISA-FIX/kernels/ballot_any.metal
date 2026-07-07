#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    bool a = simd_any(in[tid] > 100);
    bool b = simd_all(in[tid] > 0);
    out[tid] = (a?1u:0u) | (b?2u:0u);
}
