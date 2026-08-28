#include <metal_stdlib>
using namespace metal;
kernel void k(device const ulong *a [[buffer(0)]], device const ulong *b [[buffer(1)]], device const uint *c [[buffer(2)]], device ulong *out [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = c[gid] ? a[gid] : b[gid];
}
