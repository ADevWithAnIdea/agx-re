#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos; };
struct PatchU { float4x4 mvp; float displace; };
struct VOut { float4 position [[position]]; };
[[patch(quad, 4)]]
vertex VOut vMain(const device CP* cp [[buffer(0)]],
                  const device PatchU* pu [[buffer(1)]],
                  uint pid [[patch_id]], float2 uv [[position_in_patch]]) {
    const device CP* p = cp + pid*4;
    float4 a = mix(p[0].pos, p[1].pos, uv.x);
    float4 b = mix(p[2].pos, p[3].pos, uv.x);
    float4 pos = mix(a, b, uv.y);
    pos.z += pu[pid].displace * (uv.x*uv.y);
    VOut o; o.position = pu[pid].mvp * pos; return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.position; }
