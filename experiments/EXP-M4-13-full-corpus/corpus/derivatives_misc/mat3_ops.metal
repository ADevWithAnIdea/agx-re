#include <metal_stdlib>
using namespace metal;
// 3x3 matrix ops incl. transpose. Odd width (3) may pad columns to 4; watch
// for the move/shuffle pattern the compiler uses to transpose.
kernel void k(device float3* o [[buffer(0)]],
              device const float3x3* A [[buffer(1)]],
              device const float3x3* B [[buffer(2)]],
              device const float3* v [[buffer(3)]],
              uint i [[thread_position_in_grid]]) {
    float3x3 mm = A[i] * B[i];
    float3x3 t  = transpose(A[i]);
    float3   r  = mm * v[i] + t * v[i] + v[i] * B[i];
    o[i] = r;
}
