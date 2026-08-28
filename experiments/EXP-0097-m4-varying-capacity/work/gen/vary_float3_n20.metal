#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float3 v0 [[user(v0)]];
    float3 v1 [[user(v1)]];
    float3 v2 [[user(v2)]];
    float3 v3 [[user(v3)]];
    float3 v4 [[user(v4)]];
    float3 v5 [[user(v5)]];
    float3 v6 [[user(v6)]];
    float3 v7 [[user(v7)]];
    float3 v8 [[user(v8)]];
    float3 v9 [[user(v9)]];
    float3 v10 [[user(v10)]];
    float3 v11 [[user(v11)]];
    float3 v12 [[user(v12)]];
    float3 v13 [[user(v13)]];
    float3 v14 [[user(v14)]];
    float3 v15 [[user(v15)]];
    float3 v16 [[user(v16)]];
    float3 v17 [[user(v17)]];
    float3 v18 [[user(v18)]];
    float3 v19 [[user(v19)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.v0 = float3(0*0.0001+0*0.2, 0*0.0001+1*0.2, 0*0.0001+2*0.2);
    o.v1 = float3(1*0.0001+0*0.2, 1*0.0001+1*0.2, 1*0.0001+2*0.2);
    o.v2 = float3(2*0.0001+0*0.2, 2*0.0001+1*0.2, 2*0.0001+2*0.2);
    o.v3 = float3(3*0.0001+0*0.2, 3*0.0001+1*0.2, 3*0.0001+2*0.2);
    o.v4 = float3(4*0.0001+0*0.2, 4*0.0001+1*0.2, 4*0.0001+2*0.2);
    o.v5 = float3(5*0.0001+0*0.2, 5*0.0001+1*0.2, 5*0.0001+2*0.2);
    o.v6 = float3(6*0.0001+0*0.2, 6*0.0001+1*0.2, 6*0.0001+2*0.2);
    o.v7 = float3(7*0.0001+0*0.2, 7*0.0001+1*0.2, 7*0.0001+2*0.2);
    o.v8 = float3(8*0.0001+0*0.2, 8*0.0001+1*0.2, 8*0.0001+2*0.2);
    o.v9 = float3(9*0.0001+0*0.2, 9*0.0001+1*0.2, 9*0.0001+2*0.2);
    o.v10 = float3(10*0.0001+0*0.2, 10*0.0001+1*0.2, 10*0.0001+2*0.2);
    o.v11 = float3(11*0.0001+0*0.2, 11*0.0001+1*0.2, 11*0.0001+2*0.2);
    o.v12 = float3(12*0.0001+0*0.2, 12*0.0001+1*0.2, 12*0.0001+2*0.2);
    o.v13 = float3(13*0.0001+0*0.2, 13*0.0001+1*0.2, 13*0.0001+2*0.2);
    o.v14 = float3(14*0.0001+0*0.2, 14*0.0001+1*0.2, 14*0.0001+2*0.2);
    o.v15 = float3(15*0.0001+0*0.2, 15*0.0001+1*0.2, 15*0.0001+2*0.2);
    o.v16 = float3(16*0.0001+0*0.2, 16*0.0001+1*0.2, 16*0.0001+2*0.2);
    o.v17 = float3(17*0.0001+0*0.2, 17*0.0001+1*0.2, 17*0.0001+2*0.2);
    o.v18 = float3(18*0.0001+0*0.2, 18*0.0001+1*0.2, 18*0.0001+2*0.2);
    o.v19 = float3(19*0.0001+0*0.2, 19*0.0001+1*0.2, 19*0.0001+2*0.2);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float s = in.v0.x + in.v1.x + in.v2.x + in.v3.x + in.v4.x + in.v5.x + in.v6.x + in.v7.x + in.v8.x + in.v9.x + in.v10.x + in.v11.x + in.v12.x + in.v13.x + in.v14.x + in.v15.x + in.v16.x + in.v17.x + in.v18.x + in.v19.x;
    return float4(s, 0, 0, 1);
}
