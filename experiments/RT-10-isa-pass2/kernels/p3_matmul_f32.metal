#include <metal_stdlib>
using namespace metal;
// RT-10 Part3: fp32 8x8 simdgroup_matrix multiply_accumulate D = A*B + C.
// DIFFERENT from RT-5 (which read back one scalar of mad_f32): here A,B,C are loaded
// from device buffers with distinct known values, so A/B/C/dst/accum splices are all observable.
kernel void k(device float* dOut [[buffer(0)]],
              device const float* aIn [[buffer(1)]],
              device const float* bIn [[buffer(2)]],
              device const float* cIn [[buffer(3)]],
              uint tid [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, C, D;
    simdgroup_load(A, aIn, 8);
    simdgroup_load(B, bIn, 8);
    simdgroup_load(C, cIn, 8);
    simdgroup_multiply_accumulate(D, A, B, C);   // D = A*B + C
    simdgroup_store(D, dOut, 8);
}
