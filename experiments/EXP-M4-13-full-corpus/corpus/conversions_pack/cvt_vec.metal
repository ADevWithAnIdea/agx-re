// conversions_pack: vectorized numeric conversions (4-lane packed convert forms).
// Isolates int4->float4, uint4->float4, float4->int4, float4->half4 vector converts.
#include <metal_stdlib>
using namespace metal;
kernel void cvt_vec(device float4* o [[buffer(0)]],
                    device const int4* ia [[buffer(1)]],
                    device const uint4* ua [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    int4  n = ia[i];
    uint4 u = ua[i];
    float4 a = float4(n);        // 4x i32 -> f32
    float4 b = float4(u);        // 4x u32 -> f32
    int4   c = int4(a * 2.0f);   // 4x f32 -> i32
    half4  d = half4(a);         // 4x f32 -> f16
    o[i] = a + b + float4(c) + float4(d);
}
