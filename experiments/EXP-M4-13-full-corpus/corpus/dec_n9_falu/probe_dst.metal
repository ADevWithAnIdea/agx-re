#include <metal_stdlib>
using namespace metal;
kernel void k_fma4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
   device const float4* b[[buffer(2)]], device const float4* c[[buffer(3)]], uint i[[thread_position_in_grid]]){
   o[i]=fma(a[i],b[i],c[i]); }
kernel void k_mul4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
   device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]*b[i]; }
kernel void k_add4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
   device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
