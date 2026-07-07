#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int n = in[tid];
    int acc = 0;
    int i = 0;
    while (i < n) {
        acc += i * i;
        i++;
    }
    out[tid] = acc;
}
