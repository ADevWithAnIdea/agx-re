#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// make_filled_simdgroup_matrix + per-thread element access (thread_elements()) —
// surface the constructor/broadcast and the per-lane element read/modify path.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    simdgroup_float8x8 C = make_filled_simdgroup_matrix<float, 8, 8>(2.0f);
    simdgroup_float8x8 A;
    simdgroup_load(A, a, 8);
    simdgroup_multiply_accumulate(C, A, C, C);
    // per-thread element view: read/modify/write the lane-owned fragment
    auto e = C.thread_elements();
    e[0] = e[0] * 3.0f + 1.0f;
    simdgroup_store(C, o, 8);
}
