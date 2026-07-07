#include <metal_stdlib>
using namespace metal;
// RT-10 Part2: short-circuit && and || (each operand has a side-effecting divergent evaluation).
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int x = in[tid];
    int y = in[tid ^ 1u];
    int r = 0;
    if (x > 0 && y > 0 && (x + y) < 100) r += 1;
    if (x < 0 || y < 0 || (x * y) > 500) r += 10;
    if ((x & 1) && (y & 1) || (x == y)) r += 100;
    out[tid] = r;
}
