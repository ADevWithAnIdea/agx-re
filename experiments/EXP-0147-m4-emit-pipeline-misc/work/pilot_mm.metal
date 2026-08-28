#include <metal_stdlib>
using namespace metal;
kernel void k_mad_f32(device float *out [[buffer(0)]],
                      const device float *a [[buffer(1)]],
                      const device float *b [[buffer(2)]],
                      const device float *c [[buffer(3)]],
                      uint tid [[thread_position_in_threadgroup]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    simdgroup_load(C, c, 8);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, out, 8);
}
