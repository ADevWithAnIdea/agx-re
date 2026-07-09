#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos; };
struct VOut { float4 position [[position]]; };
[[patch(quad, 4)]]
vertex VOut vMain(const device CP* cp [[buffer(0)]], uint pid [[patch_id]],
                  half2 uv [[position_in_patch]]) {
    VOut o; o.position = cp[pid*4+0].pos*float(uv.x); return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.position; }
