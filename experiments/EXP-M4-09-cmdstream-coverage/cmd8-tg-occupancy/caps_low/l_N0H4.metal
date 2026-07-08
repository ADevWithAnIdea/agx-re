#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
  float x=a[i];
  float t=a[i+1]*1.000001f;
  half ht=(half)(a[i+2]*0.5f);
  half h0=(half)(x*0.7000f);
  half h1=(half)(x*0.7300f);
  half h2=(half)(x*0.7600f);
  half h3=(half)(x*0.7900f);
  for(int j=0;j<6;j++){
    h0=fma(h0,ht,h0*(half)0.5h+(half)0.0000h);
    h1=fma(h1,ht,h1*(half)0.5h+(half)0.0100h);
    h2=fma(h2,ht,h2*(half)0.5h+(half)0.0200h);
    h3=fma(h3,ht,h3*(half)0.5h+(half)0.0300h);
  }
  o[i]=(float)h0+(float)h1+(float)h2+(float)h3;
}
