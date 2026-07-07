#include <metal_stdlib>
using namespace metal;
// Exclusive prefix sum: out[lane] = 0+..+(lane-1); out[0]=0.
kernel void k(device uint* out [[buffer(0)]],
              uint lane [[thread_index_in_threadgroup]]) {
    uint v = lane;
    out[lane] = simd_prefix_exclusive_sum(v);
}
