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
  half h0=(half)(x*0.7000f);
  half h1=(half)(x*0.7300f);
  half h2=(half)(x*0.7600f);
  half h3=(half)(x*0.7900f);
  half h4=(half)(x*0.8200f);
  for(int j=0;j<6;j++){
    s0=fma(s0,t,s0*0.5f+0.000000f);
    s1=fma(s1,t,s1*0.5f+0.010000f);
    s2=fma(s2,t,s2*0.5f+0.020000f);
    s3=fma(s3,t,s3*0.5f+0.030000f);
    h0=fma(h0,ht,h0*(half)0.5h+(half)0.0000h);
    h1=fma(h1,ht,h1*(half)0.5h+(half)0.0100h);
    h2=fma(h2,ht,h2*(half)0.5h+(half)0.0200h);
    h3=fma(h3,ht,h3*(half)0.5h+(half)0.0300h);
    h4=fma(h4,ht,h4*(half)0.5h+(half)0.0400h);
  }
  o[i]=s0+s1+s2+s3+(float)h0+(float)h1+(float)h2+(float)h3+(float)h4;
}
