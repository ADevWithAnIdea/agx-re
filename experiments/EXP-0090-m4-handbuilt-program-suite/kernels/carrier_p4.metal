#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* fin [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float a0=fin[tid+0], a1=fin[tid+1], a2=fin[tid+2], a3=fin[tid+3];
    float a4=fin[tid+4], a5=fin[tid+5], a6=fin[tid+6], a7=fin[tid+7];
    float a8=fin[tid+8], a9=fin[tid+9];
    out[tid+0]=a0+a1; out[tid+1]=a2+a3; out[tid+2]=a4+a5; out[tid+3]=a6+a7;
    out[tid+4]=a8+a9; out[tid+5]=a0*a2; out[tid+6]=a4*a6; out[tid+7]=a8*a1;
    out[tid+8]=a3*a5; out[tid+9]=a7*a9; out[tid+10]=a0; out[tid+11]=a9;
}
