#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* a [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid] = a[tid] + 7;
}
