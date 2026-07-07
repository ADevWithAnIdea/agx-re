#include <metal_stdlib>
using namespace metal;

kernel void k(device const uint *a [[buffer(0)]],
              device const uint *b [[buffer(1)]],
              device const uint *c [[buffer(2)]],
              device uint *out [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = min3(a[gid], b[gid], c[gid]);
}
