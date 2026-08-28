#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float4 v0 [[user(v0)]];
    float4 v1 [[user(v1)]];
    float4 v2 [[user(v2)]];
    float4 v3 [[user(v3)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.v0 = float4(0*0.0001+0*0.2, 0*0.0001+1*0.2, 0*0.0001+2*0.2, 0*0.0001+3*0.2);
    o.v1 = float4(1*0.0001+0*0.2, 1*0.0001+1*0.2, 1*0.0001+2*0.2, 1*0.0001+3*0.2);
    o.v2 = float4(2*0.0001+0*0.2, 2*0.0001+1*0.2, 2*0.0001+2*0.2, 2*0.0001+3*0.2);
    o.v3 = float4(3*0.0001+0*0.2, 3*0.0001+1*0.2, 3*0.0001+2*0.2, 3*0.0001+3*0.2);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float s = in.v0.x + in.v1.x + in.v2.x + in.v3.x;
    return float4(s, 0, 0, 1);
}
