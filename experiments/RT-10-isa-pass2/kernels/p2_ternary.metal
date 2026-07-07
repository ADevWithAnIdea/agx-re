#include <metal_stdlib>
using namespace metal;
// RT-10 Part2: chained ternaries (nested select cascade).
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    int x = in[tid];
    int r = (x < 0)   ? -1
          : (x == 0)  ? 0
          : (x < 10)  ? 1
          : (x < 100) ? 2
          : (x < 1000)? 3
          :             4;
    out[tid] = r * ((x & 1) ? 7 : 9);
}
