#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// Chained MMA accumulation (K-loop shape): repeated multiply_accumulate into the
// same accumulator — the tight tile-MMA sequence a GEMM inner loop emits.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 C = simdgroup_float8x8(0);
    for (uint k = 0; k < 4; ++k) {
        simdgroup_float8x8 A, B;
        simdgroup_load(A, a + k * 64, 8);
        simdgroup_load(B, b + k * 64, 8);
        simdgroup_multiply_accumulate(C, A, B, C);
    }
    simdgroup_store(C, o, 8);
}
