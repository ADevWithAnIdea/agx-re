#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    uint layer [[render_target_array_index]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.layer = (4294967295u);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return float4(1,1,1,1);
}
