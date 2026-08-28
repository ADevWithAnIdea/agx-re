#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float4 v0 [[user(v0)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.v0 = float4(0*0.0001+0*0.2, 0*0.0001+1*0.2, 0*0.0001+2*0.2, 0*0.0001+3*0.2);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float s = in.v0.x;
    return float4(s, 0, 0, 1);
}
