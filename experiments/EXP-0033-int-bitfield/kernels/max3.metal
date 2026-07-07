#include <metal_stdlib>
using namespace metal;

kernel void k(device const int *a [[buffer(0)]],
              device const int *b [[buffer(1)]],
              device const int *c [[buffer(2)]],
              device int *out [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = max3(a[gid], b[gid], c[gid]);
}
