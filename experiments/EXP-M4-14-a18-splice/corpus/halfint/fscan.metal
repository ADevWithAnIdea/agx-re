#include <metal_stdlib>
using namespace metal;
kernel void k_fmin(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=min(a[i],b[i]);}
kernel void k_fmax(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=max(a[i],b[i]);}
kernel void k_frcp(device const float* a[[buffer(0)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=1.0f/a[i];}
kernel void k_frsqrt(device const float* a[[buffer(0)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=rsqrt(a[i]);}
kernel void k_ffma(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device const float* c[[buffer(3)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fma(a[i],b[i],c[i]);}
kernel void k_fabs(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fabs(a[i])+b[i];}
kernel void k_ffloor(device const float* a[[buffer(0)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=floor(a[i]);}
kernel void k_ffract(device const float* a[[buffer(0)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fract(a[i]);}
kernel void k_fmadsat(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device const float* c[[buffer(3)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=saturate(fma(a[i],b[i],c[i]));}
kernel void k_fmix(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device const float* c[[buffer(3)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=mix(a[i],b[i],c[i]);}
kernel void k_frint(device const float* a[[buffer(0)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=rint(a[i]);}
