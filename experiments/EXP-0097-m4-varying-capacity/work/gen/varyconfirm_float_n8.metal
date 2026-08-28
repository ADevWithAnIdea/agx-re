#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float v0 [[user(v0)]];
    float v1 [[user(v1)]];
    float v2 [[user(v2)]];
    float v3 [[user(v3)]];
    float v4 [[user(v4)]];
    float v5 [[user(v5)]];
    float v6 [[user(v6)]];
    float v7 [[user(v7)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.v0 = 0*0.0001+0*0.2;
    o.v1 = 1*0.0001+0*0.2;
    o.v2 = 2*0.0001+0*0.2;
    o.v3 = 3*0.0001+0*0.2;
    o.v4 = 4*0.0001+0*0.2;
    o.v5 = 5*0.0001+0*0.2;
    o.v6 = 6*0.0001+0*0.2;
    o.v7 = 7*0.0001+0*0.2;
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float s = in.v0 + in.v1 + in.v2 + in.v3 + in.v4 + in.v5 + in.v6 + in.v7;
    return float4(s, 0, 0, 1);
}
