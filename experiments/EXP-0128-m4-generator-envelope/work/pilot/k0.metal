#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device int* a [[buffer(1)]],
              device int* b [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    int x = a[tid];
    int y = b[tid];
    int z = x + y;
    out[tid] = z;
}
