#include <metal_stdlib>
using namespace metal;

kernel void k(device const uint *a [[buffer(0)]],
              device const uint *n [[buffer(1)]],
              device uint *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    uint x = a[gid]; uint s = n[gid] & 31u;
    out[gid] = (x << s) | (x >> (32u - s));
}
