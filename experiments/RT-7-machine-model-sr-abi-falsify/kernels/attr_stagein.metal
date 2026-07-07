#include <metal_stdlib>
using namespace metal;
struct VIn { float3 pos [[attribute(0)]]; float4 col [[attribute(1)]]; };
struct VOut { float4 position [[position]]; float4 color [[user(locn0)]]; };
vertex VOut v_main(VIn in [[stage_in]]) {
    VOut o; o.position = float4(in.pos, 1.0); o.color = in.col; return o;
}
fragment float4 f_main(VOut in [[stage_in]]) { return in.color; }
