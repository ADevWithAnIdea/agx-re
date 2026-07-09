#include <metal_stdlib>
using namespace metal;
// LOD-query intrinsics calculate_clamped_lod / calculate_unclamped_lod. These
// map to a texture LOD-compute instruction (derivative-driven, no fetch).
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      texture2d<float> tex [[texture(0)]],
                      sampler s [[sampler(0)]]) {
    float lc = tex.calculate_clamped_lod(s, in.uv);
    float lu = tex.calculate_unclamped_lod(s, in.uv);
    return float4(lc, lu, lc - lu, 1.0);
}
