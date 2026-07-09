#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// EXTRAPOLATE: bfloat simdgroup matrix tile MMA — does HW expose a bf16 cooperative op?
kernel void kmain(device bfloat* o [[buffer(0)]],
                  device const bfloat* a [[buffer(1)]],
                  device const bfloat* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_matrix<bfloat, 8, 8> A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    C = simdgroup_matrix<bfloat, 8, 8>(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8);
}
