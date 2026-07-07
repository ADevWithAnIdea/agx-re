#include <metal_stdlib>
using namespace metal;
// RT-10 Part2: SWITCH statement (multi-way divergence). New form vs RT-ISA-FIX (if/else/for/while).
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int x = in[tid];
    int r;
    switch (x & 3) {
        case 0: r = x + 7;      break;
        case 1: r = x * 3;      break;
        case 2: r = x - 11;     break;
        default: r = x ^ 0x55;  break;
    }
    out[tid] = r;
}
