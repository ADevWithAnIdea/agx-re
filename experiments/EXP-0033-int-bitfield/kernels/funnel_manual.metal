#include <metal_stdlib>
using namespace metal;

kernel void k(device const uint *a [[buffer(0)]],
              device const uint *b [[buffer(1)]],
              device const uint *n [[buffer(2)]],
              device uint *out [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    uint s = n[gid] & 31u;
    out[gid] = (a[gid] << s) | (b[gid] >> (32u - s));
}
