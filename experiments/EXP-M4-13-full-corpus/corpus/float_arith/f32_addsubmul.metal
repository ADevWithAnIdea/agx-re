#include <metal_stdlib>
using namespace metal;
// Isolate the primitive fp32 ALU dyads: add, sub (add+negate modifier), mul.
// scalar + vector widths so the packed/vectorized ALU forms are surfaced too.
kernel void k_add(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void k_sub(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] - b[i];
}
kernel void k_mul(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                  device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
kernel void k_add_v2(device float2* o[[buffer(0)]], device const float2* a[[buffer(1)]],
                     device const float2* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void k_add_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                     device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void k_mul_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                     device const float4* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
