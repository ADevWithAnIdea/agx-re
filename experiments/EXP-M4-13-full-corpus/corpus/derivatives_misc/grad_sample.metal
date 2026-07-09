#include <metal_stdlib>
using namespace metal;
// Explicit-gradient texture sample: tex.sample(..., gradient2d(dpdx,dpdy)).
// The AGX texture-sample instruction gains gradient operands here, a distinct
// form vs sample_lod / plain sample.
struct VOut { float4 pos [[position]]; float2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      texture2d<float> tex [[texture(0)]],
                      sampler s [[sampler(0)]]) {
    float2 dpdx = dfdx(in.uv) * 1.3;
    float2 dpdy = dfdy(in.uv) * 0.7;
    return tex.sample(s, in.uv, gradient2d(dpdx, dpdy));
}
