#include <metal_stdlib>
using namespace metal;
kernel void k(device const ulong *a [[buffer(0)]], device uint *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = ctz(a[gid]);
}
