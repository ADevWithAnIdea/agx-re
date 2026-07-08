#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
  float x=a[i];
  float t=a[i+1]*1.000001f;
  float s0=x*1.001000f+0.500000f;
  float s1=x*1.002000f+0.510000f;
  float e0=a[i+3]*1.000000f;
  float e1=a[i+4]*1.001000f;
  for(int j=0;j<6;j++){
    s0=fma(s0,t,s0*0.5f+0.000000f);
    s1=fma(s1,t,s1*0.5f+0.010000f);
  }
  o[i]=s0+s1+e0+e1;
}
