#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float4 flatcolor [[flat]] [[user(flatcolor)]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;

    // Strip verts: 0,1,2,3 -> tri0=(0,1,2) tri1=(1,2,3) (Metal strip winding).
    float2 pos[4] = { float2(-1,-1), float2(-1,1), float2(0,-1), float2(0,1) };
    o.position = float4(pos[vid]*float2(1,1) + float2(vid>=2 ? 1.0 : 0.0, 0), 0, 1);
    float4 colors[4] = { float4(1,0,0,1), float4(0,1,0,1), float4(0,0,1,1), float4(1,1,0,1) };
    o.flatcolor = colors[vid];

    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return in.flatcolor;
}
