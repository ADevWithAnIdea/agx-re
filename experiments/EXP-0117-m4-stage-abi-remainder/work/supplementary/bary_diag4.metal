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

struct BaryOut { float4 raw [[color(0)]]; float4 manual [[color(1)]]; };
fragment BaryOut f_bary(float3 b [[barycentric_coord]], constant float3 &tags [[buffer(0)]]) {
    BaryOut o;
    o.raw = float4(b, 0.0);
    float m = b.x * tags.x + b.y * tags.y + b.z * tags.z;
    o.manual = float4(m, 0.0, 0.0, 0.0);
    return o;
}
