#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos; };
struct VOut { float4 position [[position]]; };
[[patch(quad, 4)]]
vertex VOut vMain(const device CP* cp [[buffer(0)]], uint pid [[patch_id]],
                  float2 uv [[position_in_patch]]) {
    const device CP* p = cp + pid*4;
    float4 a = mix(p[0].pos, p[1].pos, uv.x);
    float4 b = mix(p[2].pos, p[3].pos, uv.x);
    VOut o; o.position = mix(a, b, uv.y); return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.position; }
