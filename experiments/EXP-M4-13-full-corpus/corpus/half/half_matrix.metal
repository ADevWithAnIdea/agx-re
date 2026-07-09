// OWN-SHADER. Isolate half matrix arithmetic (metal half2x2/half4x4 * vec -> fma trees).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half4* o[[buffer(0)]],
              device const half4* cols[[buffer(1)]],
              device const half4* vin[[buffer(2)]],
              uint i[[thread_position_in_grid]]) {
    half4x4 M = half4x4(cols[i*4+0], cols[i*4+1], cols[i*4+2], cols[i*4+3]);
    half4   v = vin[i];
    half4   mv = M * v;              // 4x4 half matrix * vec (fma tree)
    half2x2 N = half2x2(half2(v.x, v.y), half2(v.z, v.w));
    half2   nv = N * v.xy;          // 2x2 half matrix * vec
    half4x4 M2 = M * M;             // matrix * matrix
    o[i] = mv + half4(nv, nv) + M2[0];
}
