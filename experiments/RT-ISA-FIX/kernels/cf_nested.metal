#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int n = in[tid];
    int acc = 0;
    for (int i = 0; i < n; i++) {
        if (i & 1) {
            for (int j = 0; j < i; j++) {
                if (j == 3) continue;
                acc += j;
            }
        } else {
            acc -= i;
        }
    }
    out[tid] = acc;
}
