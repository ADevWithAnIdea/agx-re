#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// EXTRAPOLATE: non-8x8 tile size (16x16). Metal typically only defines 8x8; this
// probes whether a wider cooperative tile compiles. Failure = negative result.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  device const float* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_matrix<float, 16, 16> A, B, C;
    simdgroup_load(A, a, 16);
    simdgroup_load(B, b, 16);
    C = simdgroup_matrix<float, 16, 16>(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 16);
}
