#include <metal_stdlib>
using namespace metal;
// RT-10 Part3: HALF 8x8 simdgroup_matrix D = A*B + C (dtype byte+1 = 0x00 expected).
kernel void k(device half* dOut [[buffer(0)]],
              device const half* aIn [[buffer(1)]],
              device const half* bIn [[buffer(2)]],
              device const half* cIn [[buffer(3)]],
              uint tid [[thread_position_in_grid]]) {
    simdgroup_half8x8 A, B, C, D;
    simdgroup_load(A, aIn, 8);
    simdgroup_load(B, bIn, 8);
    simdgroup_load(C, cIn, 8);
    simdgroup_multiply_accumulate(D, A, B, C);
    simdgroup_store(D, dOut, 8);
}
