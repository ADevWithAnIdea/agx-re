#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos; };
struct VOut { float4 position [[position]]; };
[[patch(triangle, 3)]]
vertex VOut vMain(const device CP* cp [[buffer(0)]], uint pid [[patch_id]],
                  float3 b [[position_in_patch]]) {
    VOut o; o.position = cp[pid*3+0].pos*b.x + cp[pid*3+1].pos*b.y + cp[pid*3+2].pos*b.z; return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.position; }
