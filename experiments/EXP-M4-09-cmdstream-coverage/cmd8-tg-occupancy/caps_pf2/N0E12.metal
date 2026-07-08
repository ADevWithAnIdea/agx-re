#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
  float x=a[i];
  float t=a[i+1]*1.000001f;
  float e0=a[i+3]*1.000000f;
  float e1=a[i+4]*1.001000f;
  float e2=a[i+5]*1.002000f;
  float e3=a[i+6]*1.003000f;
  float e4=a[i+7]*1.004000f;
  float e5=a[i+8]*1.005000f;
  float e6=a[i+9]*1.006000f;
  float e7=a[i+10]*1.007000f;
  float e8=a[i+11]*1.008000f;
  float e9=a[i+12]*1.009000f;
  float e10=a[i+13]*1.010000f;
  float e11=a[i+14]*1.011000f;
  for(int j=0;j<6;j++){
  }
  o[i]=e0+e1+e2+e3+e4+e5+e6+e7+e8+e9+e10+e11;
}
