#include <metal_stdlib>
using namespace metal;
// RT-10 Part3: fp32 8x8 PURE multiply (no accumulate) D = A*B. accumulate-enable byte+11 bit0
// should be CLEAR here vs SET in p3_matmul_f32 -> the byte-diff pins the accum bit.
kernel void k(device float* dOut [[buffer(0)]],
              device const float* aIn [[buffer(1)]],
              device const float* bIn [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, D;
    simdgroup_load(A, aIn, 8);
    simdgroup_load(B, bIn, 8);
    simdgroup_multiply(D, A, B);   // D = A*B   (no +C)
    simdgroup_store(D, dOut, 8);
}
