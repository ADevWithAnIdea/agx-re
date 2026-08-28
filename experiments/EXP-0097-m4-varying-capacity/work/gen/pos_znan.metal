#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float4 pos[3] = { float4(-1,-1,0,1), float4(3,-1,0,1), float4(-1,3,0,1) };
    float4 p = pos[vid];
    if (vid == 0) {
        p[2] = (0.0/0.0);
    }
    o.position = p;
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return float4(1,1,1,1);
}
