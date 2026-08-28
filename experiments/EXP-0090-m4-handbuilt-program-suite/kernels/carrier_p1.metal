#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* fin [[buffer(1)]],
              device int* iA [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float a0=fin[tid+0], a1=fin[tid+1], a2=fin[tid+2], a3=fin[tid+3];
    float a4=fin[tid+4], a5=fin[tid+5], a6=fin[tid+6], a7=fin[tid+7];
    out[tid+0]=a0+a1; out[tid+1]=a2+a3; out[tid+2]=a4+a5; out[tid+3]=a6+a7;
    out[tid+4]=a0*a1; out[tid+5]=a2*a3; out[tid+6]=a4*a5; out[tid+7]=a6*a7;
    out[tid+8]=a0-a1; out[tid+9]=a2-a3; out[tid+10]=a0; out[tid+11]=a1;
    int ia0 = iA[tid+0], ia1 = iA[tid+1];
    out[tid+12] = float(ia0 + ia1);
}
