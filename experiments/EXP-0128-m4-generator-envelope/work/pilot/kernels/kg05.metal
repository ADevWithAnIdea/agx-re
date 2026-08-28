#include <metal_stdlib>
using namespace metal;
kernel void k(device int* zout [[buffer(0)]], device int* xbuf [[buffer(1)]], device int* ybuf [[buffer(2)]], device int* sinkout [[buffer(3)]], device int* g0buf [[buffer(4)]], device int* g1buf [[buffer(5)]], device int* g2buf [[buffer(6)]], device int* g3buf [[buffer(7)]], device int* g4buf [[buffer(8)]], uint tid [[thread_position_in_grid]]) {
    int g0 = g0buf[tid];
    int g1 = g1buf[tid];
    int g2 = g2buf[tid];
    int g3 = g3buf[tid];
    int g4 = g4buf[tid];
    int x = xbuf[tid];
    int y = ybuf[tid];
    int z = x + y;
    zout[tid] = z;
    sinkout[tid] = g0 | g1 | g2 | g3 | g4;
}