#include <metal_stdlib>
using namespace metal;
// Fused multiply-add family: the fma() intrinsic (true FMA), the a*b+c pattern
// (contraction), and sign-negated FMA variants that exercise the FMA operand
// negate/absolute modifiers.
kernel void k_fma(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                  uint i[[thread_position_in_grid]]) {
    o[i] = fma(a[i], b[i], c[i]);
}
kernel void k_fma_neg(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                      uint i[[thread_position_in_grid]]) {
    o[i] = fma(-a[i], b[i], -c[i]);   // negate on multiplicand and addend
}
kernel void k_fma_nfnsub(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                         device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                         uint i[[thread_position_in_grid]]) {
    o[i] = fma(a[i], b[i], -c[i]) - fma(-a[i], b[i], c[i]);
}
kernel void k_mad_contract(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                           device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                           uint i[[thread_position_in_grid]]) {
    o[i] = a[i] * b[i] + c[i];        // contraction candidate -> ffma
}
kernel void k_fma_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                     device const float4* b[[buffer(2)]], device const float4* c[[buffer(3)]],
                     uint i[[thread_position_in_grid]]) {
    o[i] = fma(a[i], b[i], c[i]);
}
