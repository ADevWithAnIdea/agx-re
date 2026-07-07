#include <metal_stdlib>
using namespace metal;

kernel void k(device const int *a [[buffer(0)]],
              device int *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    int v = a[gid];
    if (v == 3) { out[gid] = 100; } else { out[gid] = 200; }
}
