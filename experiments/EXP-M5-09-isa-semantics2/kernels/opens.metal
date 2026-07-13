// EXP-M5-09: small opens from EXP-M5-07.
// - 0xNe compact ALU op-select isolation (add/mul/mov)
// - 0xb7 provoke attempt
// - 12B integer-add delta
// CLEAN-ROOM: OUR OWN MSL. One op per kernel where possible.
#include <metal_stdlib>
using namespace metal;

// half add: half datapath tends to emit compact 4B ALU forms (0xNe).
kernel void h_add(device const half *a [[buffer(0)]], device const half *b [[buffer(1)]],
                  device half *o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
kernel void h_mul(device const half *a [[buffer(0)]], device const half *b [[buffer(1)]],
                  device half *o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
kernel void h_mov(device const half *a [[buffer(0)]], device half *o [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = a[i];
}
// half FMA
kernel void h_fma(device const half *a [[buffer(0)]], device const half *b [[buffer(1)]],
                  device const half *c [[buffer(2)]], device half *o [[buffer(3)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = fma(a[i], b[i], c[i]);
}
// integer add (clean single iadd) -> 12B-form check
kernel void i_add(device const int *a [[buffer(0)]], device const int *b [[buffer(1)]],
                  device int *o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
// integer add with a constant -> different iadd form
kernel void i_addk(device const int *a [[buffer(0)]], device int *o [[buffer(1)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + 12345;
}
// signed clamp / min-max may provoke 0xb7 quad/simd-adjacent family
kernel void q_reduce_signed(device const int *a [[buffer(0)]], device int *o [[buffer(1)]],
                            uint i [[thread_position_in_grid]]) {
    o[i] = quad_max(a[i]) + quad_min(a[i]);
}
