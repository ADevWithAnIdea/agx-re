#include <metal_stdlib>
using namespace metal;
kernel void t_exp2(device float* o, device const float* a, uint g[[thread_position_in_grid]]){ o[g]=exp2(a[g]); }
kernel void t_log2(device float* o, device const float* a, uint g[[thread_position_in_grid]]){ o[g]=log2(a[g]); }
kernel void t_sqrt(device float* o, device const float* a, uint g[[thread_position_in_grid]]){ o[g]=sqrt(a[g]); }
kernel void t_rsqrt(device float* o, device const float* a, uint g[[thread_position_in_grid]]){ o[g]=rsqrt(a[g]); }
kernel void t_sin(device float* o, device const float* a, uint g[[thread_position_in_grid]]){ o[g]=sin(a[g]); }
kernel void t_recip(device float* o, device const float* a, uint g[[thread_position_in_grid]]){ o[g]=1.0f/a[g]; }
