#include <metal_stdlib>
using namespace metal;
kernel void k(device int* zout [[buffer(0)]], device int* xbuf [[buffer(1)]], device int* ybuf [[buffer(2)]], uint tid [[thread_position_in_grid]]) {
    int x = xbuf[tid];
    int y = ybuf[tid];
    int z = x + y;
    zout[tid] = z;
}