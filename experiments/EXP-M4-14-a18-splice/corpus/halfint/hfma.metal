#include <metal_stdlib>
using namespace metal;
// half fma variants that might grow the 0x10 op to 8 or 12 bytes
kernel void k_hfma(device const half* a[[buffer(0)]],device const half* b[[buffer(1)]],device const half* c[[buffer(3)]],device half* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fma(a[i],b[i],c[i]);}
kernel void k_hfmasat(device const half* a[[buffer(0)]],device const half* b[[buffer(1)]],device const half* c[[buffer(3)]],device half* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=saturate(fma(a[i],b[i],c[i]));}
kernel void k_hfma_neg(device const half* a[[buffer(0)]],device const half* b[[buffer(1)]],device const half* c[[buffer(3)]],device half* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fma(-a[i],b[i],c[i]);}
kernel void k_hfma_abs(device const half* a[[buffer(0)]],device const half* b[[buffer(1)]],device const half* c[[buffer(3)]],device half* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fma(fabs(a[i]),b[i],c[i]);}
// mixed 32/16: one operand f32 -> may force wider form
kernel void k_hfma_mix(device const half* a[[buffer(0)]],device const float* b[[buffer(1)]],device const half* c[[buffer(3)]],device half* o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=fma(a[i],half(b[i]),c[i]);}
