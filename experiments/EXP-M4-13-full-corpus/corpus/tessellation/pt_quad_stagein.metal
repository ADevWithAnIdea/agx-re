#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos [[attribute(0)]]; float4 col [[attribute(1)]]; };
struct VOut { float4 position [[position]]; float4 col; };
[[patch(quad, 4)]]
vertex VOut vMain(patch_control_point<CP> cp [[stage_in]], float2 uv [[position_in_patch]]) {
    float4 a = mix(cp[0].pos, cp[1].pos, uv.x);
    float4 b = mix(cp[2].pos, cp[3].pos, uv.x);
    float4 c0 = mix(cp[0].col, cp[1].col, uv.x);
    float4 c1 = mix(cp[2].col, cp[3].col, uv.x);
    VOut o; o.position = mix(a, b, uv.y); o.col = mix(c0, c1, uv.y); return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.col; }
