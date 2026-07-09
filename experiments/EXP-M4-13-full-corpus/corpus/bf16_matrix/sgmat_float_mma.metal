#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// simdgroup_float8x8: load + multiply_accumulate + store — canonical FP32 tile MMA.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    C = simdgroup_float8x8(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8);
}
