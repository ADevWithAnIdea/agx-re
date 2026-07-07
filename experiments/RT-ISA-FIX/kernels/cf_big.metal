#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int n = in[tid];
    int acc = 0;
    for (int i = 0; i < n; i++) {
        if (i & 1) {
            int j = 0;
            while (j < i) {
                if (j == 5) { j++; continue; }
                if (j > 40) break;
                acc += in[j & 7] * j;
                j++;
            }
        } else if (i > 20) {
            acc -= i * 3;
        } else {
            acc += i;
        }
    }
    if (acc < 0) acc = -acc;
    out[tid] = acc;
}
