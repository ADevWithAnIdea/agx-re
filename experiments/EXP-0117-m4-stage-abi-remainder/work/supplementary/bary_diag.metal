#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut v_bary(uint vid [[vertex_id]]) {
    VOut o;
    float2 p[3] = { float2(-0.6,-0.6), float2(0.6,-0.6), float2(0.0,0.6) };
    float  w[3] = { 1.0, 2.0, 4.0 };
    uint i = vid % 3;
    o.position = float4(p[i] * w[i], 0.0, w[i]);
    return o;
}
struct DiagOut { float4 raw [[color(0)]]; float4 pos [[color(1)]]; };
fragment DiagOut f_diag(float4 pos [[position]], float3 b [[barycentric_coord]]) {
    DiagOut o;
    o.raw = float4(b, 0.0);
    o.pos = pos;
    return o;
}
