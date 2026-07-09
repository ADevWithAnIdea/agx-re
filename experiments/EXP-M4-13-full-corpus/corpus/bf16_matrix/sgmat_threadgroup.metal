#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// simdgroup matrix load/store via THREADGROUP address space (not device) — different
// addressing / barrier interplay for the tile load.
kernel void kmain(device float* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  threadgroup float* tg [[threadgroup(0)]],
                  uint li [[thread_index_in_threadgroup]],
                  uint i  [[thread_position_in_grid]]) {
    tg[li] = a[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    simdgroup_float8x8 A, C;
    simdgroup_load(A, tg, 8);
    C = simdgroup_float8x8(0);
    simdgroup_multiply_accumulate(C, A, A, C);
    simdgroup_store(C, o, 8);
}
