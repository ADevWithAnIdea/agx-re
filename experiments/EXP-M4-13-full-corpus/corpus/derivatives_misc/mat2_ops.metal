#include <metal_stdlib>
using namespace metal;
// 2x2 matrix ops: mul, transpose, matrix+matrix (component add), reconstruct
// from columns. Narrowest matrix width — minimal fma fan-out.
kernel void k(device float2* o [[buffer(0)]],
              device const float2x2* A [[buffer(1)]],
              device const float2x2* B [[buffer(2)]],
              device const float2* v [[buffer(3)]],
              uint i [[thread_position_in_grid]]) {
    float2x2 mm = A[i] * B[i];
    float2x2 t  = transpose(A[i]);
    float2x2 sum = A[i] + B[i];
    float2x2 rc = float2x2(v[i], v[i].yx);
    float2 r = mm * v[i] + t * v[i] + sum[0] + rc[1];
    o[i] = r;
}
