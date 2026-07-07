#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out  [[buffer(0)]],
              device float* out2 [[buffer(1)]],
              const device float* v [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    float a0=v[gid*8+0],a1=v[gid*8+1],a2=v[gid*8+2],a3=v[gid*8+3];
    float a4=v[gid*8+4],a5=v[gid*8+5],a6=v[gid*8+6],a7=v[gid*8+7];
    out[gid]  = a0 + a1;
    out2[gid] = a2 + a3 + a4 + a5 + a6 + a7;
}
