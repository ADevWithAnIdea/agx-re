#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
kernel void k(device const float *a [[buffer(0)]],
              device float *out     [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    simdgroup_float8x8 m;
    simdgroup_load(m, a, 8);
    simdgroup_float8x8 n;
    simdgroup_load(n, a + 64, 8);
    simdgroup_float8x8 r = simdgroup_float8x8(0);
    simdgroup_multiply_accumulate(r, m, n, r);
    simdgroup_store(r, out, 8);
}
