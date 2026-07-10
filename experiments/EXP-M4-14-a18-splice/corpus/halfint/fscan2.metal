#include <metal_stdlib>
using namespace metal;
kernel void k_copysign(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=copysign(a[i],b[i]);}
kernel void k_select(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device const float* c[[buffer(3)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=select(a[i],b[i],c[i]>0.0f);}
kernel void k_ldexp(device const float* a[[buffer(0)]],device const int* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=ldexp(a[i],b[i]);}
kernel void k_sign(device const float* a[[buffer(0)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=sign(a[i]);}
kernel void k_trunc(device const float* a[[buffer(0)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=trunc(a[i]);}
kernel void k_fdim(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fdim(a[i],b[i]);}
kernel void k_step(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=step(a[i],b[i]);}
kernel void k_clamp(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device const float* c[[buffer(3)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=clamp(a[i],b[i],c[i]);}
kernel void k_negmul(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=(-a[i])*(-b[i]);}
kernel void k_absmul(device const float* a[[buffer(0)]],device const float* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fabs(a[i])*fabs(b[i]);}
kernel void k_dot2(device const float2* a[[buffer(0)]],device const float2* b[[buffer(1)]],device float* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=dot(a[i],b[i]);}
