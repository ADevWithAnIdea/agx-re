#include <metal_stdlib>
using namespace metal;
kernel void k(device const float*a[[buffer(0)]],device const float*b[[buffer(1)]],device float*o[[buffer(2)]],uint i[[thread_position_in_grid]]){float acc[24];for(int j=0;j<24;j++)acc[j]=a[i]*float(j+1)+b[i];float s=0;for(int j=0;j<24;j++)s+=acc[j]*acc[(j+7)%24];o[i]=s;}
