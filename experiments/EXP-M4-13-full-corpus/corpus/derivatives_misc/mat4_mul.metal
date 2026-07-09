#include <metal_stdlib>
using namespace metal;
// 4x4 matrix algebra: mat*mat, mat*vec (column), vec*mat (row), mat*scalar.
// Matrix multiply lowers to dense fma chains; probes fma operand packing at
// the widest common matrix size.
kernel void k(device float4* o [[buffer(0)]],
              device const float4x4* A [[buffer(1)]],
              device const float4x4* B [[buffer(2)]],
              device const float4* v [[buffer(3)]],
              uint i [[thread_position_in_grid]]) {
    float4x4 mm = A[i] * B[i];      // matrix * matrix
    float4   mv = mm * v[i];        // matrix * column vector
    float4   vm = v[i] * A[i];      // row vector * matrix
    float4x4 ms = A[i] * 3.5f;      // matrix * scalar
    o[i] = mv + vm + ms[0] + ms[3];
}
