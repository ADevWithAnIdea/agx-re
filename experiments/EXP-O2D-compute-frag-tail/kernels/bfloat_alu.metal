#include <metal_stdlib>
using namespace metal;

// ============ Sub-experiment 3: bfloat general (non-matrix) ALU ============
// Does bfloat add/mul/fma/convert reuse the fp16 0x10 group with a type bit,
// use a distinct group, or lower to fp32? Compare against half + float refs.

// ---- bfloat scalar ----
kernel void bf_add(device bfloat* o [[buffer(0)]],
                   device const bfloat* a [[buffer(1)]],
                   device const bfloat* b [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void bf_mul(device bfloat* o [[buffer(0)]],
                   device const bfloat* a [[buffer(1)]],
                   device const bfloat* b [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
kernel void bf_fma(device bfloat* o [[buffer(0)]],
                   device const bfloat* a [[buffer(1)]],
                   device const bfloat* b [[buffer(2)]],
                   device const bfloat* c [[buffer(3)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = bfloat(fma(a[i], b[i], c[i]));
}
// convert bfloat<->float
kernel void bf_to_f32(device float* o [[buffer(0)]],
                      device const bfloat* a [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
kernel void f32_to_bf(device bfloat* o [[buffer(0)]],
                      device const float* a [[buffer(1)]],
                      uint i [[thread_position_in_grid]]) {
    o[i] = bfloat(a[i]);
}
// bfloat2 packed
kernel void bf2_add(device bfloat2* o [[buffer(0)]],
                    device const bfloat2* a [[buffer(1)]],
                    device const bfloat2* b [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void bf2_mul(device bfloat2* o [[buffer(0)]],
                    device const bfloat2* a [[buffer(1)]],
                    device const bfloat2* b [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
// bfloat transcendental (does bfloat go through fp32 SFU?)
kernel void bf_rsqrt(device bfloat* o [[buffer(0)]],
                     device const bfloat* a [[buffer(1)]],
                     uint i [[thread_position_in_grid]]) {
    o[i] = bfloat(rsqrt(a[i]));
}

// ---- half references (0x10 native-half group) ----
kernel void h_add(device half* o [[buffer(0)]],
                  device const half* a [[buffer(1)]],
                  device const half* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void h_mul(device half* o [[buffer(0)]],
                  device const half* a [[buffer(1)]],
                  device const half* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
kernel void h_fma(device half* o [[buffer(0)]],
                  device const half* a [[buffer(1)]],
                  device const half* b [[buffer(2)]],
                  device const half* c [[buffer(3)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = fma(a[i], b[i], c[i]);
}

// ---- float references (0x09 group) ----
kernel void f_add(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void f_mul(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
kernel void f_fma(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  device const float* c [[buffer(3)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = fma(a[i], b[i], c[i]);
}
