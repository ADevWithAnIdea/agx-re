#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
kernel void mat_ls(device float* out, device const float* a, uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 m;
    simdgroup_load(m, a, 8);
    simdgroup_store(m, out, 8);
}
kernel void mat_mul(device float* out, device const float* a, device const float* b, uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    simdgroup_multiply(C, A, B);
    simdgroup_store(C, out, 8);
}
kernel void mat_load2(device float* out, device const float* a, uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 m0, m1;
    simdgroup_load(m0, a, 8);
    simdgroup_load(m1, a + 64, 8);
    simdgroup_store(m0, out, 8);
    simdgroup_store(m1, out + 64, 8);
}
