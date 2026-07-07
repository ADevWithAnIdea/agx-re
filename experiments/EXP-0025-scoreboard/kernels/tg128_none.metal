#include <metal_stdlib>
using namespace metal;
kernel void k(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[128];
    scratch[lid] = a[gid];
    out[gid] = scratch[127 - lid];
}
