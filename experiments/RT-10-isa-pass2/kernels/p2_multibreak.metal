#include <metal_stdlib>
using namespace metal;
// RT-10 Part2: nested loops with MULTIPLE breaks at different depths + an early outer break.
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int n = in[tid];
    int acc = 0;
    for (int i = 0; i < n; i++) {
        if (i > 50) break;               // outer break #1
        for (int j = 0; j < n; j++) {
            if (j > i) break;            // inner break #1
            if (acc > 1000) break;       // inner break #2
            acc += i * j;
        }
        if (acc < -500) break;           // outer break #2
    }
    out[tid] = acc;
}
