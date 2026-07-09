#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// simdgroup_load with a non-zero matrix_origin (sub-tile offset) and a wider
// elements_per_row stride — exercises strided/offset tile addressing.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 16, ulong2(8, 0));   // offset origin, stride 16
    simdgroup_load(B, b, 16, ulong2(0, 8));
    C = simdgroup_float8x8(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 16, ulong2(4, 4));
}
