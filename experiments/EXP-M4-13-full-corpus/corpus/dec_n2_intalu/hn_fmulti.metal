#include <metal_stdlib>
using namespace metal;
kernel void m(device float* o[[buffer(0)]],
              device const float* a[[buffer(1)]],
              device const float* b[[buffer(2)]],
              uint i[[thread_position_in_grid]]) {
    float m0=min(a[i+0],b[i+0]); float m1=min(a[i+1],b[i+1]);
    float m2=min(a[i+2],b[i+2]); float m3=min(a[i+3],b[i+3]);
    o[i]=m0*1.0+m1*2.0+m2*4.0+m3*8.0;
}
