#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
  float x=a[i];
  float t=a[i+1]*1.000001f;
  float s0=x*1.001000f+0.500000f;
  float s1=x*1.002000f+0.510000f;
  float s2=x*1.003000f+0.520000f;
  float s3=x*1.004000f+0.530000f;
  float s4=x*1.005000f+0.540000f;
  float s5=x*1.006000f+0.550000f;
  float s6=x*1.007000f+0.560000f;
  float s7=x*1.008000f+0.570000f;
  float s8=x*1.009000f+0.580000f;
  float s9=x*1.010000f+0.590000f;
  float s10=x*1.011000f+0.600000f;
  float s11=x*1.012000f+0.610000f;
  float s12=x*1.013000f+0.620000f;
  float s13=x*1.014000f+0.630000f;
  float s14=x*1.015000f+0.640000f;
  float s15=x*1.016000f+0.650000f;
  float s16=x*1.017000f+0.660000f;
  float s17=x*1.018000f+0.670000f;
  float s18=x*1.019000f+0.680000f;
  float s19=x*1.020000f+0.690000f;
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
    s9=fma(s9,t,s9*0.5f+0.090000f);
    s10=fma(s10,t,s10*0.5f+0.100000f);
    s11=fma(s11,t,s11*0.5f+0.110000f);
    s12=fma(s12,t,s12*0.5f+0.120000f);
    s13=fma(s13,t,s13*0.5f+0.130000f);
    s14=fma(s14,t,s14*0.5f+0.140000f);
    s15=fma(s15,t,s15*0.5f+0.150000f);
    s16=fma(s16,t,s16*0.5f+0.160000f);
    s17=fma(s17,t,s17*0.5f+0.170000f);
    s18=fma(s18,t,s18*0.5f+0.180000f);
    s19=fma(s19,t,s19*0.5f+0.190000f);
  }
  o[i]=s0+s1+s2+s3+s4+s5+s6+s7+s8+s9+s10+s11+s12+s13+s14+s15+s16+s17+s18+s19;
}
