#include <metal_stdlib>
using namespace metal;
kernel void k(device int* zout [[buffer(0)]], device int* xbuf [[buffer(1)]], device int* ybuf [[buffer(2)]], device int* p0buf [[buffer(3)]], device int* p1buf [[buffer(4)]], device int* p0out [[buffer(5)]], device int* p1out [[buffer(6)]], uint tid [[thread_position_in_grid]]) {
    int p0 = p0buf[tid] + 1;
    int p1 = p1buf[tid] + 2;
    p0out[tid] = p0;
    p1out[tid] = p1;
    int x = xbuf[tid];
    int y = ybuf[tid];
    int z = x + y;
    zout[tid] = z;
}