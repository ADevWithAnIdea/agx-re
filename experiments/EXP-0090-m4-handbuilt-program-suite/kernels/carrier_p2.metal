#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* membuf [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float a0=membuf[tid+0], a1=membuf[tid+1], a2=membuf[tid+2], a3=membuf[tid+3];
    out[tid+0]=a0+a1; out[tid+1]=a2+a3; out[tid+2]=a0*a2; out[tid+3]=a1*a3;
}
