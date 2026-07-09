#include <metal_stdlib>
using namespace metal;
// Clean-room op-select probes for the low-nibble-9 float 2-source ALU.
// Each kernel isolates ONE float primitive so the byte+2 op-select can be
// attributed by byte-diff. OUR OWN MSL (EXP-M4-13 R2, n9 family).

kernel void k_add(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
kernel void k_mul(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]*b[i]; }
kernel void k_sub(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]-b[i]; }
kernel void k_rsub(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=b[i]-a[i]; }
kernel void k_fma(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
    uint i[[thread_position_in_grid]]){ o[i]=fma(a[i],b[i],c[i]); }
kernel void k_madexpr(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
    uint i[[thread_position_in_grid]]){ o[i]=a[i]*b[i]+c[i]; }
kernel void k_mulimm(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    uint i[[thread_position_in_grid]]){ o[i]=a[i]*3.0f; }
kernel void k_addimm(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    uint i[[thread_position_in_grid]]){ o[i]=a[i]+3.0f; }
kernel void k_muluni(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    constant float& k[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]*k; }
kernel void k_adduni(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    constant float& k[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]+k; }
kernel void k_satadd(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=saturate(a[i]+b[i]); }
kernel void k_satmul(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=saturate(a[i]*b[i]); }
kernel void k_dot4(device float* o[[buffer(0)]], device const float4* a[[buffer(1)]],
    device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=dot(a[i],b[i]); }
kernel void k_mul4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
    device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]*b[i]; }
kernel void k_add4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
    device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
kernel void k_div(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
    device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]/b[i]; }
