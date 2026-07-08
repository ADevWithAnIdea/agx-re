#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
  float x=a[i];
  float t=a[i+1]*1.000001f;
  half ht=(half)(a[i+2]*0.5f);
  float s0=x*1.001000f+0.500000f;
  half h0=(half)(x*0.7000f);
  for(int j=0;j<6;j++){
    s0=fma(s0,t,s0*0.5f+0.000000f);
    h0=fma(h0,ht,h0*(half)0.5h+(half)0.0000h);
  }
  o[i]=s0+(float)h0;
}
