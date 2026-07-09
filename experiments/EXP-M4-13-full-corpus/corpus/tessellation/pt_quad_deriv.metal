#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos [[attribute(0)]]; };
struct VOut { float4 position [[position]]; float3 nrm; };
[[patch(quad, 4)]]
vertex VOut vMain(patch_control_point<CP> cp [[stage_in]], float2 uv [[position_in_patch]]) {
    float4 a=mix(cp[0].pos,cp[1].pos,uv.x), b=mix(cp[2].pos,cp[3].pos,uv.x);
    float4 pos = mix(a,b,uv.y);
    // analytic partials of bilinear patch
    float3 dU = mix(cp[1].pos-cp[0].pos, cp[3].pos-cp[2].pos, uv.y).xyz;
    float3 dV = (b - a).xyz;
    VOut o; o.position = pos; o.nrm = normalize(cross(dU, dV)); return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return float4(i.nrm,1); }
