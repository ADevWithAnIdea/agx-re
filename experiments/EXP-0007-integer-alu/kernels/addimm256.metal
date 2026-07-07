#include <metal_stdlib>
using namespace metal;

kernel void k(device const int *a [[buffer(0)]],
              device int *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + 256;
}
