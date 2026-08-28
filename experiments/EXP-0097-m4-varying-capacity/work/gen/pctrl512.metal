#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float psize [[point_size]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    o.position = float4(0, 0, 0, 1); // NDC center -> screen center of the target
    o.psize = (512.0);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return float4(1,1,1,1);
}
