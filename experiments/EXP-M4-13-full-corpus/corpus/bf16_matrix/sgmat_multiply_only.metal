#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// simdgroup_multiply (NO accumulate) — isolate the pure MUL tile op vs the MMA.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    simdgroup_multiply(C, A, B);
    simdgroup_store(C, o, 8);
}
