#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;

// 8x8 simdgroup matmul: D = A*B (+ C).
// Callers fill A[i][j]=i, B[i][j]=j, C[i][j]=1000 so:
//   (A*B)[i][j] = sum_k i*j = 8*i*j     (varies with i AND j)
//   (B*A)[i][j] = sum_k k*k = 140       (constant everywhere)
//   (A*A)[i][j] = sum_k i*k = 28*i      (varies with row i only)
//   (B*B)[i][j] = sum_k k*j = 28*j      (varies with col j only)
// C accumulate adds +1000 to every element.
// All four products + the accumulate are individually distinguishable, so
// splicing the operand-select bytes reveals exactly which field picks A/B/C.
kernel void k(device const float* A [[buffer(0)]],
              device const float* B [[buffer(1)]],
              device const float* C [[buffer(2)]],
              device float* D       [[buffer(3)]],
              uint tid [[thread_index_in_threadgroup]]) {
    simdgroup_float8x8 a, b, c, d;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(d, a, b, c);
    simdgroup_store(d, D, 8);
}
