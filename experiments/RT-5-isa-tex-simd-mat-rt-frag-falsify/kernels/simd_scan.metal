#include <metal_stdlib>
using namespace metal;

// Inclusive prefix sum: out[lane] = 0+1+...+lane = lane*(lane+1)/2.
// Exclusive would be that minus lane. Reveals byte+7 shape (scan vs reduce).
kernel void k(device uint* out [[buffer(0)]],
              uint lane [[thread_index_in_threadgroup]]) {
    uint v = lane;
    out[lane] = simd_prefix_inclusive_sum(v);
}
