#include <metal_stdlib>
using namespace metal;
kernel void cs_tgmem(device uint* out [[buffer(0)]],
                      threadgroup uchar* dyn [[threadgroup(0)]],
                      uint tid [[thread_position_in_grid]]) {
    if (tid == 0) { dyn[0] = 7; out[0] = (uint)dyn[0]; }
}
