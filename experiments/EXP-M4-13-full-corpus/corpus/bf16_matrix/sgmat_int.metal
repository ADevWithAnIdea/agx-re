#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// EXTRAPOLATE: integer element cooperative matrix (int8x8). Probes whether an
// INT MMA (dot-product style) tile exists. Failure = negative result.
kernel void kmain(device int* o [[buffer(0)]],
                  device const int* a [[buffer(1)]],
                  device const int* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_matrix<int, 8, 8> A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    C = simdgroup_matrix<int, 8, 8>(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8);
}
