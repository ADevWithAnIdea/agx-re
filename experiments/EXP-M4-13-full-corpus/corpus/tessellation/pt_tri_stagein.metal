#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos [[attribute(0)]]; float3 nrm [[attribute(1)]]; };
struct VOut { float4 position [[position]]; float3 nrm; };
[[patch(triangle, 3)]]
vertex VOut vMain(patch_control_point<CP> cp [[stage_in]], float3 b [[position_in_patch]]) {
    VOut o;
    o.position = cp[0].pos*b.x + cp[1].pos*b.y + cp[2].pos*b.z;
    o.nrm = normalize(cp[0].nrm*b.x + cp[1].nrm*b.y + cp[2].nrm*b.z);
    return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return float4(i.nrm,1); }
