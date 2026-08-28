#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device int* a [[buffer(1)]],
              device int* b [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    int p0 = a[tid + 10u] * 3 + 1;
    int p1 = a[tid + 11u] * 3 + 2;
    int x = a[tid + 900u];
    int y = b[tid + 900u];
    int z = x + y;
    out[tid] = z + (p0 + p1);
}