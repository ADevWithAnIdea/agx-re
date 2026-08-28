#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float4 flatcolor [[flat]] [[user(flatcolor)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;

    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    float4 colors[3] = { float4(1,0,0,1), float4(0,1,0,1), float4(0,0,1,1) };
    o.flatcolor = colors[vid];

    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return in.flatcolor;
}
