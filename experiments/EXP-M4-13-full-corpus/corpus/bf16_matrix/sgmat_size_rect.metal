#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// EXTRAPOLATE: rectangular tile (8 rows x 16 cols) MMA shape. Probes non-square
// cooperative tiles. Failure = negative result.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_matrix<float, 16, 8> A;   // <T, Cols, Rows>
    simdgroup_matrix<float, 8, 16> B;
    simdgroup_matrix<float, 8, 8>  C;
    simdgroup_load(A, a, 16);
    simdgroup_load(B, b, 8);
    C = simdgroup_matrix<float, 8, 8>(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8);
}
