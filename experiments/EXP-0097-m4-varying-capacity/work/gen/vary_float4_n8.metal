#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float4 v0 [[user(v0)]];
    float4 v1 [[user(v1)]];
    float4 v2 [[user(v2)]];
    float4 v3 [[user(v3)]];
    float4 v4 [[user(v4)]];
    float4 v5 [[user(v5)]];
    float4 v6 [[user(v6)]];
    float4 v7 [[user(v7)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.v0 = float4(0*0.0001+0*0.2, 0*0.0001+1*0.2, 0*0.0001+2*0.2, 0*0.0001+3*0.2);
    o.v1 = float4(1*0.0001+0*0.2, 1*0.0001+1*0.2, 1*0.0001+2*0.2, 1*0.0001+3*0.2);
    o.v2 = float4(2*0.0001+0*0.2, 2*0.0001+1*0.2, 2*0.0001+2*0.2, 2*0.0001+3*0.2);
    o.v3 = float4(3*0.0001+0*0.2, 3*0.0001+1*0.2, 3*0.0001+2*0.2, 3*0.0001+3*0.2);
    o.v4 = float4(4*0.0001+0*0.2, 4*0.0001+1*0.2, 4*0.0001+2*0.2, 4*0.0001+3*0.2);
    o.v5 = float4(5*0.0001+0*0.2, 5*0.0001+1*0.2, 5*0.0001+2*0.2, 5*0.0001+3*0.2);
    o.v6 = float4(6*0.0001+0*0.2, 6*0.0001+1*0.2, 6*0.0001+2*0.2, 6*0.0001+3*0.2);
    o.v7 = float4(7*0.0001+0*0.2, 7*0.0001+1*0.2, 7*0.0001+2*0.2, 7*0.0001+3*0.2);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float s = in.v0.x + in.v1.x + in.v2.x + in.v3.x + in.v4.x + in.v5.x + in.v6.x + in.v7.x;
    return float4(s, 0, 0, 1);
}
