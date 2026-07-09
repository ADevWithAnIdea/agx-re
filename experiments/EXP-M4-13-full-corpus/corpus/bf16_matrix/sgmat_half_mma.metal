#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// simdgroup_half8x8: FP16 tile MMA — half-precision cooperative matrix path.
kernel void kmain(device half* o [[buffer(0)]],
                  device const half* a [[buffer(1)]],
                  device const half* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_half8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    C = simdgroup_half8x8(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8);
}
