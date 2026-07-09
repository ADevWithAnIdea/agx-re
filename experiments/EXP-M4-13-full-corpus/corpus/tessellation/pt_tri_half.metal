#include <metal_stdlib>
using namespace metal;
struct CPh { half4 pos; half2 uv; };
struct VOut { float4 position [[position]]; half2 uv; };
[[patch(triangle, 3)]]
vertex VOut vMain(const device CPh* cp [[buffer(0)]], uint pid [[patch_id]],
                  float3 b [[position_in_patch]]) {
    half3 bh = half3(b);
    half4 p = cp[pid*3+0].pos*bh.x + cp[pid*3+1].pos*bh.y + cp[pid*3+2].pos*bh.z;
    half2 uv = cp[pid*3+0].uv*bh.x + cp[pid*3+1].uv*bh.y + cp[pid*3+2].uv*bh.z;
    VOut o; o.position = float4(p); o.uv = uv; return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return float4(float2(i.uv), i.position.zw); }
