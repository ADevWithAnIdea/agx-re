#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o, device const half2* a, device const half2* b,
              device const half2* c, device const half2* d, uint i[[thread_position_in_grid]]){
    half2 r0=a[i]+b[i];
    half2 r1=a[i]*b[i];
    half2 r2=c[i]+d[i];
    half2 r3=c[i]*d[i];
    o[i*4+0]=r0; o[i*4+1]=r1; o[i*4+2]=r2; o[i*4+3]=r3;
}
