#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// simdgroup_load/store with transpose=true — transposed tile addressing mode.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8, ulong2(0, 0), /*transpose=*/true);
    simdgroup_load(B, b, 8, ulong2(0, 0), /*transpose=*/false);
    C = simdgroup_float8x8(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8, ulong2(0, 0), /*transpose=*/true);
}
