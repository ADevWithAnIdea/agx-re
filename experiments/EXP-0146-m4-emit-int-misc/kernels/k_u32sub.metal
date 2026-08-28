#include <metal_stdlib>
using namespace metal;
kernel void k(device const uint *a [[buffer(0)]], device const uint *b [[buffer(1)]], device uint *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] - b[gid];
}
