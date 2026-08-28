#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}
fragment float4 f_main(VOut in [[stage_in]], device float* a [[buffer(0)]]) {
    float v = a[0];
    float x1 = v * a[1];
    float x2 = v * a[2];
    return float4(x1, x2, 0.0, 1.0);
}
