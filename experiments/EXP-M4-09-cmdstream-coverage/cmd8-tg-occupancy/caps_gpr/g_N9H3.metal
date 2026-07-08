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
  float s7=x*1.008000f+0.570000f;
  float s8=x*1.009000f+0.580000f;
  half h0=(half)(x*0.7000f);
  half h1=(half)(x*0.7300f);
  half h2=(half)(x*0.7600f);
  for(int j=0;j<6;j++){
    s0=fma(s0,t,s0*0.5f+0.000000f);
    s1=fma(s1,t,s1*0.5f+0.010000f);
    s2=fma(s2,t,s2*0.5f+0.020000f);
    s3=fma(s3,t,s3*0.5f+0.030000f);
    s4=fma(s4,t,s4*0.5f+0.040000f);
    s5=fma(s5,t,s5*0.5f+0.050000f);
    s6=fma(s6,t,s6*0.5f+0.060000f);
    s7=fma(s7,t,s7*0.5f+0.070000f);
    s8=fma(s8,t,s8*0.5f+0.080000f);
    h0=fma(h0,ht,h0*(half)0.5h+(half)0.0000h);
    h1=fma(h1,ht,h1*(half)0.5h+(half)0.0100h);
    h2=fma(h2,ht,h2*(half)0.5h+(half)0.0200h);
  }
  o[i]=s0+s1+s2+s3+s4+s5+s6+s7+s8+(float)h0+(float)h1+(float)h2;
}
