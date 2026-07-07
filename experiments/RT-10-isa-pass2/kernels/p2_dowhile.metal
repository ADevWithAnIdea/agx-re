#include <metal_stdlib>
using namespace metal;
// RT-10 Part2: do-while (guaranteed-once loop -> back-edge with a trailing guard).
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int n = in[tid];
    int acc = 0;
    int i = 0;
    do {
        acc += (i * 2 + 1);
        i++;
    } while (i < n);
    out[tid] = acc;
}
