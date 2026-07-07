#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int x = in[tid];
    int r;
    if (x > 10) {
        r = x * 2;
    } else {
        r = x + 100;
    }
    out[tid] = r;
}
