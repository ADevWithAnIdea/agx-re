#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
  float x=a[i];
  float t=a[i+1]*1.000001f;
  half ht=(half)(a[i+2]*0.5f);
  float s0=x*1.001000f+0.500000f;
  float s1=x*1.002000f+0.510000f;
  float s2=x*1.003000f+0.520000f;
  float s3=x*1.004000f+0.530000f;
  float s4=x*1.005000f+0.540000f;
  float s5=x*1.006000f+0.550000f;
  float s6=x*1.007000f+0.560000f;
  for(int j=0;j<6;j++){
    s0=fma(s0,t,s0*0.5f+0.000000f);
    s1=fma(s1,t,s1*0.5f+0.010000f);
    s2=fma(s2,t,s2*0.5f+0.020000f);
    s3=fma(s3,t,s3*0.5f+0.030000f);
    s4=fma(s4,t,s4*0.5f+0.040000f);
    s5=fma(s5,t,s5*0.5f+0.050000f);
    s6=fma(s6,t,s6*0.5f+0.060000f);
  }
  o[i]=s0+s1+s2+s3+s4+s5+s6;
}
