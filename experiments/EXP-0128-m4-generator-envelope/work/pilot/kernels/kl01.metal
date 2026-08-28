#include <metal_stdlib>
using namespace metal;
kernel void k(device int* zout [[buffer(0)]], device int* xbuf [[buffer(1)]], device int* ybuf [[buffer(2)]], device int* p0buf [[buffer(3)]], device int* p0out [[buffer(4)]], uint tid [[thread_position_in_grid]]) {
    int p0 = p0buf[tid] + 1;
    p0out[tid] = p0;
    int x = xbuf[tid];
    int y = ybuf[tid];
    int z = x + y;
    zout[tid] = z;
}