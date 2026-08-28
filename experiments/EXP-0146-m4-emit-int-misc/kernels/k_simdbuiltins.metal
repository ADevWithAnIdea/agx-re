#include <metal_stdlib>
using namespace metal;
kernel void k(device const uint *a [[buffer(0)]],
              device uint *out     [[buffer(1)]],
              uint gid [[thread_position_in_grid]],
              uint sgid [[simdgroup_index_in_threadgroup]],
              uint lane [[thread_index_in_simdgroup]]) {
    out[gid] = a[gid] + sgid + lane + simd_sum(a[gid]) + simd_ballot(a[gid] != 0u).x;
}
