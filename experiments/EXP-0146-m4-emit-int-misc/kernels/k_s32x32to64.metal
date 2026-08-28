#include <metal_stdlib>
using namespace metal;
kernel void k(device const int *a [[buffer(0)]],
              device const int *b [[buffer(1)]],
              device long *out    [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = long(a[gid]) * long(b[gid]);
}
