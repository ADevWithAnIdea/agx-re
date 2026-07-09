#include <metal_stdlib>
using namespace metal;
// Clean-room op-select probe: each kernel isolates ONE float primitive so the
// resulting low-nibble-9 op-select byte (byte+2) can be attributed. Our own MSL.

kernel void k_add(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) { o[i]=a[i]+b[i]; }
kernel void k_sub(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) { o[i]=a[i]-b[i]; }
kernel void k_mul(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) { o[i]=a[i]*b[i]; }
kernel void k_fma(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                  uint i[[thread_position_in_grid]]) { o[i]=fma(a[i],b[i],c[i]); }
kernel void k_madexpr(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                  uint i[[thread_position_in_grid]]) { o[i]=a[i]*b[i]+c[i]; }
kernel void k_negmul(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) { o[i]=-(a[i]*b[i]); }
kernel void k_nfma(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                  uint i[[thread_position_in_grid]]) { o[i]=fma(a[i],b[i],-c[i]); }
kernel void k_sat(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) { o[i]=saturate(a[i]+b[i]); }
kernel void k_satmul(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) { o[i]=saturate(a[i]*b[i]); }
kernel void k_absadd(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) { o[i]=fabs(a[i])+b[i]; }
kernel void k_mov(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) { o[i]=a[i]; }
kernel void k_neg(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) { o[i]=-a[i]; }
kernel void k_abs(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) { o[i]=fabs(a[i]); }
kernel void k_satmov(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) { o[i]=saturate(a[i]); }
kernel void k_muladd_chain(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                  device const float* d[[buffer(4)]], uint i[[thread_position_in_grid]]) {
    o[i]=a[i]*b[i]+c[i]*d[i]; }
