#include <metal_stdlib>
using namespace metal;
kernel void k(device int* zout [[buffer(0)]], device int* xbuf [[buffer(1)]], device int* ybuf [[buffer(2)]], device int* p0buf [[buffer(3)]], device int* p1buf [[buffer(4)]], device int* p2buf [[buffer(5)]], device int* p3buf [[buffer(6)]], device int* p4buf [[buffer(7)]], device int* p5buf [[buffer(8)]], device int* p0out [[buffer(9)]], device int* p1out [[buffer(10)]], device int* p2out [[buffer(11)]], device int* p3out [[buffer(12)]], device int* p4out [[buffer(13)]], device int* p5out [[buffer(14)]], uint tid [[thread_position_in_grid]]) {
    int x = xbuf[tid];
    int y = ybuf[tid];
    int p0 = p0buf[tid] + 1;
    int p1 = p1buf[tid] + 2;
    int p2 = p2buf[tid] + 3;
    int p3 = p3buf[tid] + 4;
    int p4 = p4buf[tid] + 5;
    int p5 = p5buf[tid] + 6;
    p0out[tid] = p0;
    p1out[tid] = p1;
    p2out[tid] = p2;
    p3out[tid] = p3;
    p4out[tid] = p4;
    p5out[tid] = p5;
    int z = x + y;
    zout[tid] = z;
}